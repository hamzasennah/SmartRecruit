from app.services.rules.domain_rules import get_domain_rule_section, load_domain_rules


def test_domain_rules_load_expected_sections() -> None:
    rules = load_domain_rules()

    assert {"cv", "job", "responsibility"}.issubset(rules)
    assert "power bi" in get_domain_rule_section("cv")["raw_text_skill_hints"]
    assert get_domain_rule_section("job")["technical_text_rules"]["snowflake"]["bucket"] == "mandatory"
    assert "data_processing" in get_domain_rule_section("responsibility")["concept_groups"]


def test_declared_candidate_roles_have_non_data_skill_coverage() -> None:
    cv_rules = get_domain_rule_section("cv")
    job_rules = get_domain_rule_section("job")
    roles = set(cv_rules["candidate_roles"])
    cv_hints = set(cv_rules["raw_text_skill_hints"])
    job_hints = set(job_rules["technical_text_rules"])

    assert {
        "data analyst",
        "data scientist",
        "data engineer",
        "developpeur",
        "d\u00e9veloppeur",
        "developer",
        "full stack",
        "fullstack",
        "frontend",
        "backend",
        "ingenieur",
        "ing\u00e9nieur",
        "software",
        "support",
        "consultant",
        "chef de projet",
        "project manager",
    } == roles

    role_coverage = {
        "data": {"python", "sql", "power bi", "snowflake", "dashboard"},
        "software": {"javascript", "typescript", "react", "node.js", "java", "spring boot", "docker", "api rest"},
        "support": {"itil", "ticketing", "servicenow", "active directory", "office 365", "networking"},
        "project": {"agile", "scrum", "kanban", "jira", "risk management", "requirements gathering"},
    }
    for expected_skills in role_coverage.values():
        assert expected_skills.issubset(cv_hints)
        assert expected_skills.issubset(job_hints)
