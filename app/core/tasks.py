import os
import traceback
import httpx
import logging
import asyncio
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
from sqlalchemy import select

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.models.domain import SystemConfig
from app.core.database import async_session_maker 
from app.api.v1.scheduling import orchestrator


logger = logging.getLogger("uvicorn.error")


async def fetch_government_disaster_status(city: str) -> dict:
    # 這是目前台灣最可靠的社群維護防災假 JSON 來源
    url = "https://raw.githubusercontent.com/taiwan-disaster-data/typhoon/main/status.json"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                # 同時嘗試「台」與「臺」，防止因為字體不同而匹配失敗
                city_variants = [city, city.replace("臺", "台"), city.replace("台", "臺")]
                for variant in city_variants:
                    if variant in data:
                        return data[variant]
                
                logger.warning(f"API 中找不到名為 '{city}' 的資料，現有城市：{list(data.keys())}")
    except Exception as e:
        logger.error(f"防災 API 連線失敗: {e}")

    return {"is_suspended": False, "reason": "正常上班上課"}


async def send_emergency_notification_to_slack(content: str, session: AsyncSession):
    stmt = select(SystemConfig).where(SystemConfig.key == "SLACK_EMERGENCY_WEBHOOK")
    result = await session.execute(stmt)
    config = result.scalars().first()
    webhook_url = config.value if config else ""

    if not webhook_url:
        logger.info(f"[應變廣播系統預覽]:\n{content}")
        return
        
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={"text": content})
    except Exception as e:
        logger.error(f"傳送應變通知至 Slack 失敗: {e}")


async def sync_disaster_leave_job():
    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz)
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    logger.info(f"[背景巡邏開跑] 正在檢查 {tomorrow} 台北市政府是否有放防災假公告...")
    
    status = await fetch_government_disaster_status(city="臺北市")
    
    if not status.get("is_suspended"):
        logger.info(f"巡邏結束：{tomorrow} 台北市作息正常，無發布防災假。")
        return

    logger.critical(f"[重大災害警報] 偵測到台北市明日 ({tomorrow}) 宣佈停班停課！原因: {status.get('reason')}")

    async with async_session_maker() as session:
        try:
            system_injection_input = (
                f"【系統最高級別強制指令】\n"
                f"政府已正式發布重大災害通報：{status.get('reason')}\n"
                f"請你立刻執行以下連鎖任務：\n"
                f"1. 呼叫 `check_and_apply_disaster_leave` 工具，將日期設定在明日（{tomorrow}），縣市填寫「臺北市」。這個工具會自動為明天所有的班表加上【颱風停班】的標註，絕對不會刪除任何班表，也不會排假。\n"
                f"2. 執行完成後，請為電視台內部群組撰寫一篇精準、嚴肅、繁體中文的『颱風天應變報告』，"
                f"明確告知大家「原定班表皆已保留，僅於系統中加註颱風停班（紅框標示）」，並提醒主管安排留守人力。"
            )
            
            logger.info("背景 Agent 正在通盤思考清班決策與公告撰寫...")
            response_content = await orchestrator.chat(
                session_id="system_cron_job_typhoon",
                user_message=system_injection_input
            )

            # 不管 AI 怎麼回，最後的報告直接送出廣播
            await send_emergency_notification_to_slack(response_content, session)
            logger.critical("防災假全自動備註與應變廣播程序順利完成！")
                
        except Exception as e:
            await session.rollback()
            logger.error(f"背景防災定時任務執行期間發生崩潰，已全自動回滾資料庫。錯誤原因: {str(e)}")
            logger.error(traceback.format_exc())

async def cleanup_chat_history_job():
    """定期清理超過一個月的對話紀錄"""
    logger.info("[背景維護] 啟動對話紀錄清理作業...")
    from agent.persistence.repository import SchedulingRepository
    
    async with async_session_maker() as session:
        try:
            repo = SchedulingRepository(session)
            await repo.clear_old_chat_history(days=30)
            logger.info("[背景維護] 對話紀錄清理完成（已刪除 30 天前的資料）。")
        except Exception as e:
            logger.error(f"[背景維護] 清理對話紀錄失敗: {e}")
