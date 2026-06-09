from app.prompts.templates import IMPROVE_RESUME_PROMPTS


def test_keyword_prompt_guides_transferable_software_framing():
    prompt = IMPROVE_RESUME_PROMPTS["keywords"]

    assert "transferable software/AI value" in prompt
    assert "cross-functional collaboration" in prompt
    assert "stakeholder communication" in prompt
    assert "Do NOT surface recruiting noise" in prompt


def test_full_prompt_guides_project_segmentation_and_quantification():
    prompt = IMPROVE_RESUME_PROMPTS["full"]

    assert "2-4 concise bullets per project" in prompt
    assert "quantified outcomes" in prompt
    assert "Australian-style resume writing" in prompt


def test_prompts_guide_professional_project_and_internship_bullets():
    for prompt_id in ("keywords", "full"):
        prompt = IMPROVE_RESUME_PROMPTS[prompt_id]

        assert "project and internship bullets" in prompt
        assert "worked on, helped, made, used" in prompt
        assert "do not overstate ownership" in prompt
