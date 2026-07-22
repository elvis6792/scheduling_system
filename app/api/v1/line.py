import os
import json
import logging
import httpx
import random
import string
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.api.v1.scheduling import orchestrator
from app.core.database import async_session_maker
from app.models.domain import Staff, SystemConfig, User

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


class ConfigUpdate(BaseModel):
    value: str


@router.get("/config/{key}")
async def get_config(key: str, session: AsyncSession = Depends(async_session_maker)):
    stmt = select(SystemConfig).where(SystemConfig.key == key)
    config = (await session.execute(stmt)).scalars().first()
    if not config:
        return {"key": key, "value": ""}
    return {"key": key, "value": config.value}


@router.post("/config/{key}")
async def update_config(key: str, payload: ConfigUpdate, session: AsyncSession = Depends(async_session_maker)):
    stmt = select(SystemConfig).where(SystemConfig.key == key)
    config = (await session.execute(stmt)).scalars().first()

    if config:
        config.value = payload.value
    else:
        config = SystemConfig(key=key, value=payload.value, description="系統動態設定值")
        session.add(config)

    await session.commit()
    return {"message": "設定更新成功", "key": key}


@router.post("/users/{user_id}/generate_bind_code")
async def generate_line_bind_code(user_id: int):
    
    # 直接在這裡開啟資料庫連線，不要經過 FastAPI 的 Depends
    async with async_session_maker() as session:
        
        stmt_user = select(User).where(User.id == user_id)
        user_account = (await session.execute(stmt_user)).scalars().first()
        
        if not user_account:
            raise HTTPException(status_code=404, detail="找不到該登入帳號")
            
        import random, string
        bind_code = ''.join(random.choices(string.digits, k=6))
        
        # 寫入 User 表
        user_account.line_bind_code = bind_code
        await session.commit()
        
        return {
            "message": "綁定碼產生成功",
            "bind_code": bind_code
        }


async def reply_to_line(reply_token: str, text: str, channel_access_token: str):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_access_token}"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            logger.error(f"回覆 LINE 失敗: {res.text}")


@router.post("/line/webhook")
async def line_webhook(request: Request, x_line_signature: str = Header(None), session: AsyncSession = Depends(async_session_maker)):
    stmt = select(SystemConfig).where(SystemConfig.key == "LINE_CHANNEL_ACCESS_TOKEN")
    result = await session.execute(stmt)
    config = result.scalars().first()
    channel_access_token = config.value if config else ""

    if not channel_access_token:
        logger.error("系統未設定 LINE_CHANNEL_ACCESS_TOKEN，拒絕處理 Webhook。")
        raise HTTPException(status_code=500, detail="LINE configuration missing")

    body = await request.body()
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    events = data.get("events", [])
    for event in events:
        if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        line_user_id = event.get("source", {}).get("userId")
        user_message = event.get("message", {}).get("text", "").strip()

        if not line_user_id or not reply_token:
            continue

        if user_message.startswith("綁定 "):
            bind_code = user_message.replace("綁定 ", "").strip()

            stmt = select(Staff).where(Staff.line_bind_code == bind_code)
            staff_member = (await session.execute(stmt)).scalars().first()

            if staff_member:
                staff_member.line_user_id = line_user_id
                staff_member.line_bind_code = None

                user_stmt = select(User).where(User.staff_id == staff_member.id)
                user_account = (await session.execute(user_stmt)).scalars().first()
                role_display = user_account.role if user_account else "後製技師"

                await session.commit()

                success_msg = f"綁定成功！歡迎 {staff_member.name}！\n您目前的權限為：[{role_display}]。\n現在您可以直接在這裡向排班小幫手請假或查詢班表了。"
                await reply_to_line(reply_token, success_msg, channel_access_token)
            else:
                await reply_to_line(reply_token, "綁定失敗：驗證碼錯誤或已過期，請回到排班系統重新產生。", channel_access_token)
            continue

        user_role = "staff"
        resolved_staff_name = "未知同仁"

        stmt = select(Staff).where(Staff.line_user_id == line_user_id)
        result = await session.execute(stmt)
        staff_member = result.scalars().first()

        if staff_member:
            resolved_staff_name = staff_member.name
            user_stmt = select(User).where(User.staff_id == staff_member.id)
            user_account = (await session.execute(user_stmt)).scalars().first()
            user_role = user_account.role if user_account else "staff"
        else:
            deny_msg = "【系統拒絕】\n您的 LINE 帳號尚未與電視台排班系統綁定，無法執行任何操作。請輸入「綁定 [您的驗證碼]」完成綁定。"
            await reply_to_line(reply_token, deny_msg, channel_access_token)
            continue

        logger.info(f"[LINE 雙向對話] 來自: {resolved_staff_name} | 角色: {user_role} | 訊息: {user_message}")

        try:
            response_content = await orchestrator.chat(
                session_id=line_user_id,
                user_message=user_message
            )

            await reply_to_line(reply_token, response_content, channel_access_token)

        except Exception as e:
            logger.error(f"LINE Webhook 處理 AI 推理時發生錯誤: {str(e)}")
            err_msg = "【小幫手暫時迷路了】\n系統處理您的請求時發生微小震盪，請稍後再試一次，或使用明確的繁體中文指令。"
            await reply_to_line(reply_token, err_msg, channel_access_token)

    return {"status": "ok"}