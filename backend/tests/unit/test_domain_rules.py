from app.services.rules.domain_rules import get_domain_rule_section, load_domain_rules


def test_domain_rules_load_expected_sections() -> None:
    rules = load_domain_rules()

    assert {"cv", "job", "responsibility"}.issubset(rules)
    assert "power bi" in get_domain_rule_section("cv")["raw_text_skill_hints"]
    assert get_domain_rule_section("job")["technical_text_rules"]["snowflake"]["bucket"] == "mandatory"
    assert "data_processing" in get_domain_rule_section("responsibility")["concept_groups"]
