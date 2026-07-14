from app.schemas.cv import SkillSet, StructuredCV
from app.schemas.job import RequiredSkills, StructuredJobDescription
from app.services.matching.skill_matcher import match_skills


def test_skill_matching_uses_aliases() -> None:
    cv = StructuredCV(skills=SkillSet(technical=["Python3", "Postgres"], tools=["PowerBI"]))
    job = StructuredJobDescription(required_skills=RequiredSkills(mandatory=["python", "power bi"], preferred=["sql"]))
    result = match_skills(cv, job)
    assert result["score"] >= 80
    assert "python" in result["matched"]
    assert "power bi" in result["matched"]

