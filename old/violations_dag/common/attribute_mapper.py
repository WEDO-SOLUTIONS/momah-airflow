# /common/attribute_mapper.py
from typing import Dict

# This dictionary maps DB column names to their display properties.
ATTRIBUTE_MAPPER: Dict[str, Dict[str, str]] = {

    # DB Column Name: { en: "English Caption", ar: "Arabic Caption", type: "api_type" }
    "AmanaId": {"en": "Amana ID", "ar": "معرف الأمانة", "type": "string"},
    "AmanaAr": {"en": "Amana Name (AR)", "ar": "اسم الأمانة", "type": "string"},
    "Amana_Name": {"en": "Amana Name (EN)", "ar": "اسم الأمانة (انجليزي)", "type": "string"},
    "MunicipalityId": {"en": "Municipality ID", "ar": "معرف البلدية", "type": "string"},
    "MunicipalityAr": {"en": "Municipality Name (AR)", "ar": "اسم البلدية", "type": "string"},
    "MunicipalityEng": {"en": "Municipality Name (EN)", "ar": "اسم البلدية (انجليزي)", "type": "string"}, # This will be promoted to "name" type
    "Priority_Level": {"en": "Priority Level", "ar": "مستوى الأولوية", "type": "string"},
    "Date_": {"en": "Record Date", "ar": "تاريخ التسجيل", "type": "date_time"},
    "SOURCE_TABLE": {"en": "Source Table", "ar": "الجدول المصدر", "type": "string"},
    "VPI": {"en": "VPI", "ar": "مؤشر التشوه البصري", "type": "number"},
    "COVERAGE": {"en": "Coverage", "ar": "التغطية", "type": "number"},
    "TTR": {"en": "TTR", "ar": "متوسط وقت المعالجة", "type": "number"},
    "REPEAT": {"en": "Repeat Count", "ar": "عدد التكرار", "type": "number"},
    "longitude": {"en": "Longitude", "ar": "خط الطول", "type": "number"},
    "latitude": {"en": "Latitude", "ar": "خط العرض", "type": "number"},
    "Coverage_Amana": {"en": "Coverage Amana", "ar": "تغطية الأمانة", "type": "number"},
    "VPI_Amana": {"en": "VPI Amana", "ar": "مؤشر التشوه البصري للأمانة", "type": "number"},
    "coverage_target_amana": {"en": "Coverage Target Amana", "ar": "المستهدف لتغطية الأمانة", "type": "number"},
    "vpi_target_amana": {"en": "VPI Target Amana", "ar": "المستهدف لمؤشر التشوه البصري للأمانة", "type": "number"},
    "StreetInspectedArea": {"en": "Street Inspected Area", "ar": "مساحة الشارع المفحوصة", "type": "string"},
    "StreetArea": {"en": "Street Area", "ar": "مساحة الشارع", "type": "string"},
    "UNITS_CALULCATED": {"en": "Units Calculated", "ar": "الوحدات المحسوبة", "type": "number"},
    "created_date": {"en": "Last Modified Date", "ar": "تاريخ آخر تعديل", "type": "date_time"},

}