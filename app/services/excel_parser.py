import polars as pl
from pathlib import Path
from pydantic import BaseModel, ValidationError, field_validator
from typing import List, Dict, Any
from datetime import date


class ExcelParsingError(Exception):
    def __init__(self, errors: List[Dict[str, Any]]):
        self.errors = errors
        super().__init__(f"Multiple errors occurred during Excel parsing: {len(errors)} errors.")


class LeaveRecordSchema(BaseModel):
    name: str
    department: str
    leave_date: date
    time_slot: str


class ExcelParser:

    def __init__(self):
        self.column_mapping = {
            "員工姓名": "name",
            "部門": "department",
            "休假日期": "leave_date",
            "時段": "time_slot",
        }
        self.expected_columns = list(self.column_mapping.keys())


    def parse_excel_file(self, file_path: Path) -> List[LeaveRecordSchema]:
        try:
            df = pl.read_excel(file_path)
        except Exception as e:
            raise ExcelParsingError(errors=[{"row_number": None, "error_message": f"Failed to read Excel file: {e}"}])

        df = df.with_row_index(name="original_row_index")

        missing_columns = [col for col in self.expected_columns if col not in df.columns]
        if missing_columns:
            raise ExcelParsingError(errors=[
                {"row_number": None, "error_message": f"Missing required columns: {', '.join(missing_columns)}"}
            ])

        df = df.select([
            pl.col("original_row_index"),
            *[pl.col(col).alias(self.column_mapping[col]) for col in self.expected_columns]
        ])
        df = df.with_columns(pl.col(pl.Utf8).str.strip_chars())
        df = df.drop_nulls(subset=list(self.column_mapping.values()))

        df = df.with_columns(pl.col("leave_date").alias("leave_date_original_value"))
        df = df.with_columns(pl.col("leave_date").str.to_date(format="%Y-%m-%d", strict=False).alias("leave_date"))

        date_parse_errors_df = df.filter(pl.col("leave_date").is_null())
        if not date_parse_errors_df.is_empty():
            errors = []
            for row in date_parse_errors_df.iter_rows(as_dict=True):
                errors.append({
                    "row_number": row['original_row_index'] + 1,
                    "field": "leave_date",
                    "error_message": f"Invalid date format. Expected YYYY-MM-DD, got '{row.get('leave_date_original_value', 'N/A')}'",
                    "value": row.get('leave_date_original_value', 'N/A')
                })
            raise ExcelParsingError(errors=errors)

        df = df.drop("leave_date_original_value")

        validation_errors: List[Dict[str, Any]] = []
        records: List[LeaveRecordSchema] = []

        for row_dict in df.iter_rows(as_dict=True):
            original_row_idx = row_dict.pop("original_row_index")
            try:
                records.append(LeaveRecordSchema(**row_dict))
            except ValidationError as e:
                for error in e.errors():
                    validation_errors.append({
                        "row_number": original_row_idx + 1,
                        "field": error.get("loc")[-1] if error.get("loc") else "unknown",
                        "error_message": error.get("msg", "Validation error"),
                        "value": row_dict.get(error.get("loc")[-1]) if error.get("loc") else None
                    })
            except Exception as e:
                validation_errors.append({
                    "row_number": original_row_idx + 1,
                    "error_message": f"An unexpected error occurred: {e}"
                })

        if validation_errors:
            raise ExcelParsingError(errors=validation_errors)

        return records


excel_parser = ExcelParser()
