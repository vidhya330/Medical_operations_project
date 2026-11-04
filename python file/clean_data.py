import pandas as pd
from pathlib import Path

# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW = PROJECT_ROOT / "data" / "raw"
CLEAN = PROJECT_ROOT / "data" / "cleaned"

CLEAN.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. ALL 19 REQUIRED TABLES
# ============================================================

required_tables = [
    "prescription",
    "staff_assignment",
    "ward",
    "insurance_provider",
    "patient",
    "patient_diagnostic",
    "patient_insurance",
    "drug",
    "drug_inventory",
    "drug_manufacturer",
    "employee",
    "department",
    "diagnostic_test",
    "disease",
    "doctor",
    "admission",
    "bed",
    "billing",
    "billing_detail"
]


# ============================================================
# 3. PRIMARY KEYS
# ============================================================

primary_keys = {
    "prescription": "prescription_id",
    "staff_assignment": "assignment_id",
    "ward": "ward_id",
    "insurance_provider": "insurance_provider_id",
    "patient": "patient_id",
    "patient_diagnostic": "patient_diagnostic_id",
    "patient_insurance": "patient_insurance_id",
    "drug": "drug_id",
    "drug_inventory": "inventory_id",
    "drug_manufacturer": "manufacturer_id",
    "employee": "employee_id",
    "department": "department_id",
    "diagnostic_test": "diagnostic_test_id",
    "disease": "disease_id",
    "doctor": "doctor_id",
    "admission": "admission_id",
    "bed": "bed_id",
    "billing": "bill_id",
    "billing_detail": "billing_detail_id"
}


# ============================================================
# 4. DATE COLUMNS
# ============================================================

date_columns = {
    "patient": ["date_of_birth"],
    "admission": ["admission_date", "discharge_date"],
    "billing": ["bill_date"],
    "employee": ["date_of_joining"],
    "prescription": [
        "prescription_date", "prescribed_date"
    ],
    "patient_diagnostic": [
        "diagnosis_date", "diagnostic_date"
    ],
    "patient_insurance": [
        "start_date", "end_date",
        "effective_date", "expiry_date"
    ],
    "drug_inventory": [
        "last_updated", "expiry_date", "stock_date"
    ],
    "staff_assignment": [
        "assignment_date", "start_date", "end_date"
    ],
    "billing_detail": ["service_date"]
}


# ============================================================
# 5. CANDIDATE RELATIONSHIPS
# ============================================================

relationships = [
    ("admission", "patient_id", "patient", "patient_id"),
    ("admission", "department_id", "department", "department_id"),
    ("admission", "ward_id", "ward", "ward_id"),
    ("admission", "bed_id", "bed", "bed_id"),
    ("admission", "disease_id", "disease", "disease_id"),

    ("billing", "admission_id", "admission", "admission_id"),
    ("billing_detail", "bill_id", "billing", "bill_id"),

    ("employee", "department_id", "department", "department_id"),
    ("doctor", "employee_id", "employee", "employee_id"),
    ("doctor", "department_id", "department", "department_id"),

    ("staff_assignment", "employee_id", "employee", "employee_id"),
    ("staff_assignment", "ward_id", "ward", "ward_id"),

    ("patient_diagnostic", "patient_id", "patient", "patient_id"),
    ("patient_diagnostic", "disease_id", "disease", "disease_id"),
    (
        "patient_diagnostic",
        "diagnostic_test_id",
        "diagnostic_test",
        "diagnostic_test_id"
    ),

    ("patient_insurance", "patient_id", "patient", "patient_id"),
    (
        "patient_insurance",
        "insurance_provider_id",
        "insurance_provider",
        "insurance_provider_id"
    ),

    ("drug", "manufacturer_id", "drug_manufacturer", "manufacturer_id"),
    ("drug_inventory", "drug_id", "drug", "drug_id"),
    ("prescription", "patient_id", "patient", "patient_id"),
    ("prescription", "drug_id", "drug", "drug_id")
]


# ============================================================
# 6. LOAD DATA
# ============================================================

def load_data():

    if not RAW.is_dir():
        raise FileNotFoundError(
            f"Raw folder not found: {RAW}"
        )

    missing_files = [
        name for name in required_tables
        if not (RAW / f"{name}.csv").is_file()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Missing CSV files:\n"
            + "\n".join(
                str(RAW / f"{name}.csv")
                for name in missing_files
            )
        )

    data = {}

    print("\n========== LOADING TABLES ==========")

    for name in required_tables:

        df = pd.read_csv(
            RAW / f"{name}.csv",
            low_memory=False
        )

        df.columns = df.columns.astype(str).str.strip()

        data[name] = df

        print(
            f"{name}: {len(df)} rows, "
            f"{len(df.columns)} columns"
        )

    print(f"\nTotal tables loaded: {len(data)}")

    return data


# ============================================================
# 7. STANDARDIZE TEXT
# ============================================================

def standardize_text(df):

    df = df.copy()

    for col in df.select_dtypes(
        include=["object", "string"]
    ).columns:

        df[col] = (
            df[col]
            .astype("string")
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )

        df[col] = df[col].replace("", pd.NA)

    return df


# ============================================================
# 8. PARSE DATES
# ============================================================

def parse_dates(df, columns, table_name):

    df = df.copy()

    for col in columns:

        if col not in df.columns:
            print(f"SKIPPED DATE: {table_name}.{col}")
            continue

        original_count = int(df[col].notna().sum())

        df[col] = pd.to_datetime(
            df[col],
            errors="coerce"
        )

        failed_count = (
            original_count - int(df[col].notna().sum())
        )

        print(
            f"{table_name}.{col}: "
            f"{failed_count} invalid date values"
        )

    return df


# ============================================================
# 9. DATA QUALITY SUMMARY
# ============================================================

def report_data_quality(data):

    results = []

    print("\n========== DATA QUALITY SUMMARY ==========")

    for name, df in data.items():

        results.append({
            "table": name,
            "rows_before_deduplication": len(df),
            "columns": len(df.columns),
            "exact_duplicate_rows": int(
                df.duplicated().sum()
            ),
            "missing_cells": int(
                df.isna().sum().sum()
            )
        })

    result = pd.DataFrame(results)

    result.to_csv(
        CLEAN / "data_quality_summary.csv",
        index=False
    )

    print(result.to_string(index=False))

    return result


# ============================================================
# 10. REMOVE EXACT DUPLICATES
#
# IMPORTANT:
# Removes identical rows only.
# Does not delete records merely because IDs repeat.
# ============================================================

def remove_exact_duplicates(data):

    print("\n========== REMOVING EXACT DUPLICATES ==========")

    results = []

    for name, df in data.items():

        rows_before = len(df)

        # Save duplicate records before removing them.
        duplicate_mask = df.duplicated(keep=False)
        duplicate_rows = df.loc[duplicate_mask]

        if not duplicate_rows.empty:
            duplicate_rows.to_csv(
                CLEAN / f"{name}_exact_duplicate_rows.csv",
                index=False
            )

        # Remove rows identical across all columns.
        cleaned_df = df.drop_duplicates().copy()

        rows_removed = rows_before - len(cleaned_df)

        # Replace table with deduplicated data.
        data[name] = cleaned_df

        results.append({
            "table": name,
            "rows_before": rows_before,
            "exact_duplicate_rows_removed": rows_removed,
            "rows_after": len(cleaned_df)
        })

        print(
            f"{name}: before={rows_before}, "
            f"removed={rows_removed}, "
            f"after={len(cleaned_df)}"
        )

    pd.DataFrame(results).to_csv(
        CLEAN / "duplicate_removal_summary.csv",
        index=False
    )

    print("Duplicate removal completed.")

    return data


# ============================================================
# 11. PRIMARY KEY VALIDATION
# ============================================================

def check_primary_keys(data):

    print("\n========== PRIMARY KEY CHECKS ==========")

    results = []

    for table, key in primary_keys.items():

        df = data[table]

        if key not in df.columns:

            results.append({
                "table": table,
                "primary_key": key,
                "missing_ids": None,
                "duplicate_extra_occurrences": None,
                "duplicate_groups": None,
                "status": "KEY COLUMN NOT FOUND"
            })

            print(f"Missing column: {table}.{key}")
            continue

        values = df[key]

        missing_count = int(values.isna().sum())

        valid_values = values.dropna()

        duplicate_extra = int(
            valid_values.duplicated().sum()
        )

        duplicate_groups = int(
            valid_values.value_counts().gt(1).sum()
        )

        duplicate_mask = (
            values.notna()
            & values.duplicated(keep=False)
        )

        if duplicate_mask.any():

            df.loc[duplicate_mask].to_csv(
                CLEAN / f"{table}_duplicate_key_records.csv",
                index=False
            )

        status = (
            "REVIEW REQUIRED"
            if missing_count > 0 or duplicate_extra > 0
            else "PASS"
        )

        print(
            f"{table}.{key}: "
            f"missing={missing_count}, "
            f"duplicate occurrences={duplicate_extra}, "
            f"duplicate groups={duplicate_groups}, "
            f"status={status}"
        )

        results.append({
            "table": table,
            "primary_key": key,
            "missing_ids": missing_count,
            "duplicate_extra_occurrences": duplicate_extra,
            "duplicate_groups": duplicate_groups,
            "status": status
        })

    result = pd.DataFrame(results)

    result.to_csv(
        CLEAN / "primary_key_quality.csv",
        index=False
    )

    return result


# ============================================================
# 12. FOREIGN KEY VALIDATION
# ============================================================

def check_foreign_keys(data):

    print("\n========== FOREIGN KEY CHECKS ==========")

    results = []

    for child_name, child_key, parent_name, parent_key in relationships:

        child = data[child_name]
        parent = data[parent_name]

        if (
            child_key not in child.columns
            or parent_key not in parent.columns
        ):

            results.append({
                "parent_table": parent_name,
                "parent_key": parent_key,
                "child_table": child_name,
                "child_key": child_key,
                "parent_duplicate_ids": None,
                "missing_child_ids": None,
                "invalid_references": None,
                "candidate_cardinality": "UNKNOWN",
                "status": "CHECK COLUMN NAMES"
            })

            continue

        parent_ids = (
            parent[parent_key]
            .astype("string")
            .str.strip()
        )

        child_ids = (
            child[child_key]
            .astype("string")
            .str.strip()
        )

        parent_ids = parent_ids.mask(parent_ids.eq(""))
        child_ids = child_ids.mask(child_ids.eq(""))

        valid_parent_ids = parent_ids.dropna()

        parent_duplicate_count = int(
            valid_parent_ids.duplicated().sum()
        )

        parent_unique = bool(
            parent_ids.notna().all()
            and valid_parent_ids.is_unique
        )

        missing_mask = child_ids.isna()

        invalid_mask = (
            child_ids.notna()
            & ~child_ids.isin(set(valid_parent_ids))
        )

        missing_count = int(missing_mask.sum())
        invalid_count = int(invalid_mask.sum())

        child_has_duplicates = bool(
            child_ids.dropna().duplicated().any()
        )

        if not parent_unique:
            cardinality = "PARENT KEY NOT UNIQUE"
        elif child_has_duplicates:
            cardinality = "PARENT TO CHILD: 1:* CANDIDATE"
        else:
            cardinality = (
                "CHILD KEY UNIQUE IN CURRENT DATA; "
                "VERIFY BUSINESS RULE"
            )

        status = (
            "REVIEW REQUIRED"
            if (
                not parent_unique
                or missing_count > 0
                or invalid_count > 0
            )
            else "PASS - VERIFY BUSINESS RULE"
        )

        print(
            f"{parent_name}.{parent_key} -> "
            f"{child_name}.{child_key} | "
            f"{cardinality} | "
            f"missing={missing_count} | "
            f"invalid={invalid_count}"
        )

        if invalid_mask.any():

            child.loc[invalid_mask].to_csv(
                CLEAN / (
                    f"{child_name}_{child_key}_"
                    "invalid_references.csv"
                ),
                index=False
            )

        results.append({
            "parent_table": parent_name,
            "parent_key": parent_key,
            "child_table": child_name,
            "child_key": child_key,
            "parent_duplicate_ids": parent_duplicate_count,
            "missing_child_ids": missing_count,
            "invalid_references": invalid_count,
            "candidate_cardinality": cardinality,
            "status": status
        })

    result = pd.DataFrame(results)

    result.to_csv(
        CLEAN / "foreign_key_quality.csv",
        index=False
    )

    return result


# ============================================================
# 13. CALCULATE LENGTH OF STAY
# ============================================================

def calculate_length_of_stay(data):

    print("\n========== LENGTH OF STAY ==========")

    admission = data["admission"].copy()

    if not {
        "admission_date",
        "discharge_date"
    }.issubset(admission.columns):

        print("LOS skipped: date columns are missing.")
        return admission

    admission["length_of_stay_days"] = (
        admission["discharge_date"]
        - admission["admission_date"]
    ).dt.total_seconds() / 86400

    # Ongoing admissions do not have completed LOS.
    admission.loc[
        admission["discharge_date"].isna(),
        "length_of_stay_days"
    ] = float("nan")

    negative_mask = (
        admission["length_of_stay_days"].notna()
        & (admission["length_of_stay_days"] < 0)
    )

    print("Negative LOS:", int(negative_mask.sum()))

    print(
        "Missing LOS:",
        int(admission["length_of_stay_days"].isna().sum())
    )

    if negative_mask.any():

        admission.loc[negative_mask].to_csv(
            CLEAN / "admission_invalid_los_records.csv",
            index=False
        )

    return admission


# ============================================================
# 14. CALCULATE PATIENT AGE AND AGE GROUP
# ============================================================

def calculate_patient_age(data):

    print("\n========== PATIENT AGE ==========")

    patient = data["patient"].copy()

    if "date_of_birth" not in patient.columns:
        print("Age skipped: date_of_birth missing.")
        return patient

    today = pd.Timestamp.today().normalize()
    dob = patient["date_of_birth"]

    age = (
        today.year
        - dob.dt.year
        - (
            (dob.dt.month > today.month)
            | (
                (dob.dt.month == today.month)
                & (dob.dt.day > today.day)
            )
        ).astype("float64")
    )

    patient["age"] = age.where(dob.notna())

    invalid_age = (
        patient["age"].notna()
        & ~patient["age"].between(0, 120)
    )

    print("Invalid age records:", int(invalid_age.sum()))

    if invalid_age.any():

        patient.loc[invalid_age].to_csv(
            CLEAN / "patient_invalid_age_records.csv",
            index=False
        )

    valid_age = patient["age"].where(~invalid_age)

    patient["age_group"] = pd.cut(
        valid_age,
        bins=[0, 18, 35, 60, 121],
        labels=["0-17", "18-34", "35-59", "60+"],
        right=False
    )

    return patient


# ============================================================
# 15. SAVE ALL CLEANED TABLES
# ============================================================

def save_cleaned_data(data):

    print("\n========== SAVING CLEANED TABLES ==========")

    for name, df in data.items():

        output_path = CLEAN / f"{name}_clean.csv"

        df.to_csv(
            output_path,
            index=False
        )

        print(
            f"Saved {output_path.name} | "
            f"Rows={len(df)} | "
            f"Columns={len(df.columns)}"
        )

    print(f"\nOutput folder: {CLEAN}")


# ============================================================
# 16. MAIN EXECUTION
# IMPORTANT: Function names must match exactly.
# ============================================================

def main():

    # Step 1: Load all tables.
    data = load_data()

    # Step 2: Standardize text.
    print("\n========== STANDARDIZING TEXT ==========")

    for name in data:
        data[name] = standardize_text(data[name])

    # Step 3: Parse date columns.
    print("\n========== PARSING DATES ==========")

    for name, columns in date_columns.items():

        data[name] = parse_dates(
            data[name],
            columns,
            name
        )

    # Step 4: Report initial data quality.
    report_data_quality(data)

    # Step 5: Remove exact duplicates.
    # Correct function name: remove_exact_duplicates
    data = remove_exact_duplicates(data)

    # Step 6: Check primary keys.
    pk_results = check_primary_keys(data)

    # Step 7: Check foreign keys.
    fk_results = check_foreign_keys(data)

    # Step 8: Calculate LOS.
    data["admission"] = calculate_length_of_stay(data)

    # Step 9: Calculate patient age.
    data["patient"] = calculate_patient_age(data)

    # Step 10: Save all cleaned tables.
    save_cleaned_data(data)

    # Step 11: Print validation summary.
    pk_issues = int(
        (~pk_results["status"].eq("PASS")).sum()
    )

    fk_issues = int(
        (~fk_results["status"].str.startswith(
            "PASS", na=False
        )).sum()
    )

    print("\n========== FINAL VALIDATION ==========")
    print(f"Tables processed: {len(data)}")
    print(f"Primary-key checks needing review: {pk_issues}")
    print(f"Foreign-key checks needing review: {fk_issues}")

    print("\nReports generated:")
    print("- data_quality_summary.csv")
    print("- duplicate_removal_summary.csv")
    print("- primary_key_quality.csv")
    print("- foreign_key_quality.csv")

    print("\nReview flagged records before deleting conflicting IDs.")
    print("Python does not create Power BI relationships.")
    print("\n========== PROCESS COMPLETED ==========")


if __name__ == "__main__":
    main()