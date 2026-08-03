from datetime import date

import pytest
from app.schemas.cv import Experience
from app.services.experience.duration_calculator import (
    calculate_cumulative_experience,
    calculate_experience_duration,
    enrich_experience_durations,
    parse_explicit_duration,
    parse_explicit_durations,
)
from app.services.experience.overlap_manager import calculate_total_unique_months


def test_explicit_duration() -> None:
    assert parse_explicit_duration("2 ans et 6 mois") == 30


def test_multiple_explicit_durations_in_same_entry_are_summed_without_breaking_combined_units() -> None:
    text = "Mission A (4mois) Mission B (1mois) Mission C (3mois) Contract (1 year and 3 months)"

    assert parse_explicit_durations(text) == [4, 1, 3, 15]
    assert parse_explicit_duration(text) == 23


def test_date_range_duration() -> None:
    result = calculate_experience_duration("janvier 2021", "mars 2023")
    assert result.duration_months == 27
    assert result.confidence == 0.95


def test_french_abbreviated_month_range_duration() -> None:
    result = calculate_experience_duration("Mar 2022", "Juil 2022")
    assert result.duration_months == 5
    assert result.start_date == "2022-03"
    assert result.end_date == "2022-07"


def test_full_day_month_year_date_with_depuis_is_parsed() -> None:
    result = calculate_experience_duration("Depuis 22/04/2024", "Present", today=date(2025, 4, 1))
    assert result.duration_months == 13
    assert result.start_date == "2024-04"
    assert result.end_date == "2025-04"
    assert result.start_precision == "day"
    assert result.confidence == 0.95


def test_current_marker_without_end_date_uses_today() -> None:
    result = calculate_experience_duration("Depuis 22/04/2024", None, today=date(2025, 4, 1))
    assert result.duration_months == 13
    assert result.start_date == "2024-04"
    assert result.end_date == "2025-04"
    assert result.end_precision == "present"
    assert result.calculation_source == "date_range_current_marker"


def test_single_field_date_range_is_split() -> None:
    result = calculate_experience_duration("Mar 2022 - Juil 2022", None)
    assert result.duration_months == 5
    assert result.start_date == "2022-03"
    assert result.end_date == "2022-07"
    assert result.calculation_source == "date_range_single_field"


def test_english_current_date_range_is_split() -> None:
    result = calculate_experience_duration("June 2025 - Present", None, today=date(2026, 7, 1))
    assert result.duration_months == 14
    assert result.start_date == "2025-06"
    assert result.end_date == "2026-07"


def test_year_only_dates_use_full_year_boundaries() -> None:
    result = calculate_experience_duration("2021", "2022")
    assert result.duration_months == 24
    assert result.start_date == "2021-01"
    assert result.end_date == "2022-12"
    assert result.estimated is True
    assert result.confidence == 0.60


def test_french_dotted_month_abbreviation() -> None:
    result = calculate_experience_duration("janv. 2024", "aout 2024")
    assert result.duration_months == 8
    assert result.start_date == "2024-01"
    assert result.end_date == "2024-08"


def test_unambiguous_us_numeric_date() -> None:
    result = calculate_experience_duration("04/22/2024", "Present", today=date(2025, 4, 1))
    assert result.duration_months == 13
    assert result.start_date == "2024-04"


def test_unreasonable_duration_is_reported_not_counted() -> None:
    result = calculate_experience_duration("1900", "Present", today=date(2025, 4, 1))
    assert result.duration_months is None
    assert result.confidence == 0.0
    assert result.error == "Duree d'experience non plausible: 1504 mois."


def test_overlap_periods_not_counted_twice() -> None:
    periods = [(date(2021, 1, 1), date(2022, 12, 1)), (date(2022, 6, 1), date(2023, 12, 1))]
    assert calculate_total_unique_months(periods) == 36


@pytest.mark.parametrize(
    ("start_raw", "end_raw", "expected_months", "expected_start", "expected_end"),
    [
        ("22/04/2024", "19/04/2025", 13, "2024-04", "2025-04"),
        ("De 15/05/2023 \u00e0 19/04/2024", None, 12, "2023-05", "2024-04"),
        ("01/2024 au 06/2024", None, 6, "2024-01", "2024-06"),
    ],
)
def test_numeric_french_date_ranges(start_raw: str, end_raw: str | None, expected_months: int, expected_start: str, expected_end: str) -> None:
    result = calculate_experience_duration(start_raw, end_raw)

    assert result.duration_months == expected_months
    assert result.start_date == expected_start
    assert result.end_date == expected_end
    assert result.calculation_source in {"date_range", "date_range_single_field"}


@pytest.mark.parametrize(
    ("value", "expected_months", "expected_start", "expected_end"),
    [
        ("04/2025 \u2013 present", 17, "2025-04", "2026-08"),
        ("11/2021 \u2014 02/2025", 40, "2021-11", "2025-02"),
        ("11/2021-02/2025", 40, "2021-11", "2025-02"),
        ("06/2024 \u2013 11/2024", 6, "2024-06", "2024-11"),
    ],
)
def test_numeric_month_year_ranges_with_typographic_dash(value: str, expected_months: int, expected_start: str, expected_end: str) -> None:
    result = calculate_experience_duration(value, None, today=date(2026, 8, 2))

    assert result.duration_months == expected_months
    assert result.start_date == expected_start
    assert result.end_date == expected_end
    assert result.calculation_source == "date_range_single_field"


@pytest.mark.parametrize(
    ("value", "expected_months", "expected_start", "expected_end"),
    [
        ("February 2025 \u2013 July 2025", 6, "2025-02", "2025-07"),
        ("Role: February 2025 \u2014 July 2025", 6, "2025-02", "2025-07"),
        ("JULY 2024 until August 2024", 2, "2024-07", "2024-08"),
    ],
)
def test_english_textual_date_ranges(value: str, expected_months: int, expected_start: str, expected_end: str) -> None:
    result = calculate_experience_duration(value, None)

    assert result.duration_months == expected_months
    assert result.start_date == expected_start
    assert result.end_date == expected_end


@pytest.mark.parametrize(
    ("value", "expected_months", "expected_start", "expected_end"),
    [
        ("janv. 2024 \u00e0 aout 2024", 8, "2024-01", "2024-08"),
        ("mars 2022 - juillet 2022", 5, "2022-03", "2022-07"),
        ("septembre 2021 to novembre 2021", 3, "2021-09", "2021-11"),
    ],
)
def test_french_textual_date_ranges(value: str, expected_months: int, expected_start: str, expected_end: str) -> None:
    result = calculate_experience_duration(value, None)

    assert result.duration_months == expected_months
    assert result.start_date == expected_start
    assert result.end_date == expected_end


@pytest.mark.parametrize(
    ("end_raw", "expected_months"),
    [
        ("present", 15),
        ("current", 15),
        ("ongoing", 15),
        ("actuel", 15),
        ("actuellement", 15),
    ],
)
def test_current_end_markers_use_today(end_raw: str, expected_months: int) -> None:
    result = calculate_experience_duration("June 2025", end_raw, today=date(2026, 8, 2))

    assert result.duration_months == expected_months
    assert result.end_date == "2026-08"
    assert result.end_precision == "present"


@pytest.mark.parametrize(
    ("value", "expected_months"),
    [
        ("Stage d'alternance(4mois) \u2014 2025", 4),
        ("Stage de fin d'etude - Departement de diffusion (3mois) \u2014 2023", 3),
        ("Freelance mission (1 an et 2 mois)", 14),
        ("Contract assignment (1 year and 3 months)", 15),
    ],
)
def test_explicit_duration_in_free_text_is_used_when_dates_are_missing(value: str, expected_months: int) -> None:
    result = calculate_experience_duration(value, None)

    assert result.duration_months == expected_months
    assert result.start_date is None
    assert result.end_date is None
    assert result.calculation_source == "explicit_duration_entry_text"


def test_explicit_duration_beats_year_only_pairing_when_entry_contains_duration() -> None:
    experiences = enrich_experience_durations(
        [
            Experience(job_title="Alternance data (4mois)", start_date="2023", end_date="2025"),
            Experience(job_title="Mission reporting (1mois)", start_date="2024", end_date=None),
            Experience(job_title="Projet BI (3mois)", start_date="2025", end_date="2023"),
        ]
    )

    totals = calculate_cumulative_experience(experiences)

    assert [experience.duration_months for experience in experiences] == [4, 1, 3]
    assert [experience.duration.calculation_source for experience in experiences] == [
        "explicit_duration_entry_text",
        "explicit_duration_entry_text",
        "explicit_duration_entry_text",
    ]
    assert totals.dated_months == 0
    assert totals.explicit_duration_months == 8
    assert totals.total_months == 8


@pytest.mark.parametrize(
    ("durations", "expected_total"),
    [
        (["2 mois"], 2),
        (["2 mois", "5 mois"], 7),
        (["1 mois", "2 mois", "3 mois", "4 mois", "5 mois"], 15),
    ],
)
def test_cumulative_explicit_duration_entries_sum_all_entries(durations: list[str], expected_total: int) -> None:
    experiences = enrich_experience_durations(
        [Experience(job_title=f"Mission reporting ({duration})", start_date="2025") for duration in durations]
    )

    totals = calculate_cumulative_experience(experiences)

    assert [experience.duration_months for experience in experiences] == [
        parse_explicit_duration(duration) for duration in durations
    ]
    assert totals.dated_months == 0
    assert totals.explicit_duration_months == expected_total
    assert totals.total_months == expected_total


def test_cumulative_declared_total_is_used_when_no_itemized_period_exists() -> None:
    totals = calculate_cumulative_experience([], declared_total_experience="4 ans d'experience")

    assert totals.total_months == 48
    assert totals.total_years == 4.0
    assert totals.calculation_source == "declared_total_experience"
    assert totals.calculation_status == "calculated"
    assert totals.calculated_total_months == 48


def test_cumulative_reports_not_calculable_instead_of_silent_zero() -> None:
    experiences = enrich_experience_durations([Experience(job_title="Data Analyst")])

    totals = calculate_cumulative_experience(experiences)

    assert totals.total_months == 0
    assert totals.calculated_total_months is None
    assert totals.calculation_source == "none"
    assert totals.calculation_status == "not_calculable"
    assert totals.failure_reason
    assert totals.entries[0].counted_in_total is False


def test_cumulative_multiple_dated_ranges_without_overlap() -> None:
    experiences = enrich_experience_durations(
        [
            Experience(job_title="Data Analyst", start_date="De 2020 \u00e0 2025"),
            Experience(job_title="Data Analyst", start_date="De 2026 \u00e0 2028"),
        ]
    )

    totals = calculate_cumulative_experience(experiences)

    assert [experience.duration_months for experience in experiences] == [72, 36]
    assert totals.total_months == 108
    assert totals.dated_months == 108
    assert totals.overlap_policy == "union"


def test_cumulative_overlapping_periods_use_calendar_union() -> None:
    experiences = enrich_experience_durations(
        [
            Experience(job_title="Data Analyst", start_date="janvier 2020", end_date="decembre 2022"),
            Experience(job_title="Consultant BI", start_date="janvier 2022", end_date="decembre 2023"),
        ]
    )

    totals = calculate_cumulative_experience(experiences)

    assert [experience.duration_months for experience in experiences] == [36, 24]
    assert totals.total_months == 48
    assert totals.overlap_policy == "union"


def test_cumulative_current_experience_uses_reference_today() -> None:
    experiences = enrich_experience_durations(
        [Experience(job_title="Data Analyst", start_date="Depuis avril 2024")],
        today=date(2026, 8, 2),
    )

    totals = calculate_cumulative_experience(experiences)

    assert experiences[0].duration_months == 29
    assert totals.total_months == 29
    assert experiences[0].duration.end_precision == "present"


def test_cumulative_mixes_dated_periods_and_declared_experience_duration() -> None:
    experiences = enrich_experience_durations(
        [
            Experience(job_title="Data Analyst", start_date="janvier 2021", end_date="decembre 2021"),
            Experience(job_title="Consultant BI", declared_duration="6 mois"),
        ]
    )

    totals = calculate_cumulative_experience(experiences)

    assert totals.dated_months == 12
    assert totals.explicit_duration_months == 6
    assert totals.total_months == 18


def test_cumulative_numeric_month_year_ranges_use_union_without_losing_entries() -> None:
    experiences = enrich_experience_durations(
        [
            Experience(job_title="Analyst", start_date="04/2025 \u2013 present"),
            Experience(job_title="Analyst", start_date="11/2021 \u2013 02/2025"),
            Experience(job_title="Analyst", start_date="06/2024 \u2013 11/2024"),
            Experience(job_title="Analyst", start_date="02/2024 \u2013 06/2024"),
            Experience(job_title="Analyst", start_date="06/2023 \u2013 08/2023"),
            Experience(job_title="Analyst", start_date="04/2022 \u2013 06/2022"),
        ],
        today=date(2026, 8, 2),
    )

    totals = calculate_cumulative_experience(experiences)

    assert [experience.duration_months for experience in experiences] == [17, 40, 6, 5, 3, 3]
    assert totals.period_count == 6
    assert totals.dated_months == 57
    assert totals.total_months == 57

# Role dans le projet:
# Ce fichier contient les tests unitaires pour experience. Il protege le comportement existant pendant les refactors sans appeler les services externes.
