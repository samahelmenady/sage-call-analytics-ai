"""
End-to-end integration test suite using realistic Egyptian Arabic customer support recordings.

Generates 4 realistic Egyptian Arabic call MP3 recordings with Microsoft Neural TTS (edge-tts),
including a customer-only voicemail recording to verify N/A agent evaluation & risk scoring,
and runs them through the LIVE FastAPI ASGI pipeline via httpx.AsyncClient.

Run explicitly with:
    INTEGRATION_TESTS=true pytest tests/integration/test_egyptian_e2e.py -v -s
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import edge_tts
import httpx
import pytest
from jiwer import cer, wer

from backend.main import app

pytestmark = pytest.mark.integration

_RUN_LIVE = os.getenv("INTEGRATION_TESTS", "").lower() == "true"


def _norm_ar(text: str) -> str:
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


EGYPTIAN_CALL_SCENARIOS = [
    {
        "call_id": "E2E-EG-BILLING",
        "voice": "ar-EG-SalmaNeural",
        "script": (
            "السلام عليكم، لو سمحت أنا عملت أوردر امبارح رقم أربعة خمسة اتنين "
            "واتسحب من الفيزا بتاعتي الفلوس مرتين، ولحد دلوقتي الأوردر موصلش. "
            "أهلاً بحضرتك يا فندم، أعتذر جداً لحضرتك على التأخير وخصم المبلغ مرتين. "
            "حالا هرفع طلب استرداد فوري للمبلغ الزيادة وهتوصل لحضرتك رسالة تأكيد خلال نص ساعة، "
            "والأوردر هيوصل بكرة الصبح بإذن الله."
        ),
        "expected_keywords_in_transcript": ["مرتين", "الفيزا"],
        "expected_categories": {"billing", "shipping"},
        "expected_sentiments": {"negative", "mixed"},
        "expected_priorities": {"high", "critical"},
        "expected_resolved": False,
        "expect_agent_na": False,
    },
    {
        "call_id": "E2E-EG-TECH",
        "voice": "ar-EG-ShakirNeural",
        "script": (
            "مساء الخير يا فندم، النت عندي في البيت بيفصل كل عشر دقايق من الصبح وأنا شغال من البيت. "
            "أهلاً بحضرتك، متأسف جداً على المشكلة دي. ممكن تقفل الراوتر وتفتحه بعد تلاتين ثانية "
            "وأنا هعمل تحديث للخط من عندي حالاً. تمام عملت كده واللمبة ثبتت والنت رجع شغال كويس جداً، "
            "متشكر أوي على المساعدة السريعة يا فندم."
        ),
        "expected_keywords_in_transcript": ["النت", "الراوتر"],
        "expected_categories": {"technical"},
        "expected_sentiments": {"positive", "mixed"},
        "expected_priorities": {"medium", "high"},
        "expected_resolved": True,
        "expect_agent_na": False,
    },
    {
        "call_id": "E2E-EG-RETURNS",
        "voice": "ar-EG-SalmaNeural",
        "script": (
            "أنا متضايقة جداً، دي تاني مرة أبعتولي الشاشة مكسورة في الشحن، "
            "ومش معقول أدفع مصاريف شحن تاني على غلطة من عندكم. "
            "للأسف يا فندم أنا معنديش صلاحية أعمل استرجاع من غير ما أرجع لمدير القسم، "
            "وهنحول الشكوى وهيتواصلوا معاكي خلال يومين."
        ),
        "expected_keywords_in_transcript": ["مكسوره"],
        "expected_categories": {"returns", "product_quality", "shipping"},
        "expected_sentiments": {"negative"},
        "expected_priorities": {"high", "critical"},
        "expected_resolved": False,
        "expect_agent_na": False,
    },
    {
        "call_id": "E2E-EG-VOICEMAIL",
        "voice": "ar-EG-SalmaNeural",
        "script": (
            "ألو، أنا بتصل للمرة التالتة ومحدش بيرد عليا، الأوردر بتاعي اتأخر أسبوع كامل "
            "وعدتوني توصلوه امبارح وموصلش، أنا محتاجة حد يكلمني فوراً."
        ),
        "expected_keywords_in_transcript": ["التالته", "محدش"],
        "expected_categories": {"shipping", "general_inquiry", "other"},
        "expected_sentiments": {"negative"},
        "expected_priorities": {"high", "critical"},
        "expected_resolved": False,
        "expect_agent_na": True,
    },
]


@pytest.mark.skipif(not _RUN_LIVE, reason="Set INTEGRATION_TESTS=true to run live API E2E tests")
@pytest.mark.asyncio
async def test_egyptian_arabic_end_to_end_pipeline(tmp_path: Path) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=90.0) as client:
        health = (await client.get("/api/health")).json()
        assert health["stt_ready"] is True, f"STT not ready: {health}"
        assert health["genai_ready"] is True, f"GenAI not ready: {health}"
        print(
            f"\nActive Engines -> STT: {health['stt_model']}, "
            f"GenAI: {health['genai_provider']} ({health['genai_model']})"
        )

        created_ids: list[str] = []
        try:
            for idx, scenario in enumerate(EGYPTIAN_CALL_SCENARIOS):
                mp3_path = tmp_path / f"eg_call_{idx}.mp3"
                await edge_tts.Communicate(scenario["script"], scenario["voice"]).save(str(mp3_path))
                assert mp3_path.stat().st_size > 5000

                # 1. Live Audio -> STT
                with mp3_path.open("rb") as fh:
                    stt_resp = await client.post(
                        "/api/transcribe",
                        files={"file": (mp3_path.name, fh, "audio/mpeg")},
                    )
                assert stt_resp.status_code == 200, stt_resp.text
                transcript = stt_resp.json()["transcript"]

                norm_ref = _norm_ar(scenario["script"])
                norm_hyp = _norm_ar(transcript)
                call_wer = round(float(wer(norm_ref, norm_hyp)), 4)
                call_cer = round(float(cer(norm_ref, norm_hyp)), 4)
                print(f"\n[{scenario['call_id']}] STT Transcript: {transcript}")
                print(f"[{scenario['call_id']}] Normalized WER={call_wer}, CER={call_cer}")

                for kw in scenario["expected_keywords_in_transcript"]:
                    assert _norm_ar(kw) in norm_hyp, (
                        f"Expected keyword '{kw}' missing in normalized STT output: {norm_hyp}"
                    )

                # 2. Live Transcript -> GenAI Analysis + Persistence
                ana_resp = await client.post(
                    "/api/analyze",
                    json={
                        "transcript": transcript,
                        "language": "ar",
                        "source": "audio",
                        "call_metadata": {"call_id": scenario["call_id"], "filename": mp3_path.name},
                    },
                )
                assert ana_resp.status_code == 200, ana_resp.text
                analysis = ana_resp.json()
                created_ids.append(analysis["call_id"])
                print(
                    f"[{scenario['call_id']}] Engine={analysis.get('analysis_meta', {}).get('provider')}:{analysis.get('analysis_meta', {}).get('model')} "
                    f"Category={analysis['problem']['category']} "
                    f"Priority={analysis['problem']['priority']} "
                    f"Sentiment={analysis['sentiment']['overall']}({analysis['sentiment']['score']}) "
                    f"Risk={analysis['risk_assessment']['score']}({analysis['risk_assessment']['level']}) "
                    f"Resolved={analysis['resolution']['resolved']}({analysis['resolution']['resolution_type']}) "
                    f"AgentApplicable={analysis['agent_evaluation']['applicable']} "
                    f"Agent={analysis['agent_evaluation']['overall_score']} "
                    f"Latency={analysis.get('analysis_meta', {}).get('latency_ms')}ms"
                )

                assert analysis["call_id"] == scenario["call_id"]
                assert analysis["source"] == "audio"
                assert analysis["raw_transcript"] == transcript
                assert analysis["problem"]["category"] in scenario["expected_categories"]
                assert analysis["sentiment"]["overall"] in scenario["expected_sentiments"]
                assert analysis["problem"]["priority"] in scenario["expected_priorities"]
                assert analysis["resolution"]["resolved"] == scenario["expected_resolved"]
                assert analysis["risk_assessment"] is not None
                assert 0 <= analysis["risk_assessment"]["score"] <= 100
                if scenario["expect_agent_na"]:
                    assert analysis["agent_evaluation"]["applicable"] is False
                    assert analysis["agent_evaluation"]["overall_score"] is None
                else:
                    assert analysis["agent_evaluation"]["applicable"] is True
                    assert analysis["agent_evaluation"]["overall_score"] is not None
                assert len(analysis["recommendations"]) >= 1
                assert len(analysis["key_insights"]) >= 1

            # 3. Verify Dashboard Analytics Consistency (including N/A exclusion!)
            calls_resp = await client.get("/api/calls?limit=50")
            assert calls_resp.status_code == 200
            stored_ids = {c["call_id"] for c in calls_resp.json()}
            assert set(created_ids).issubset(stored_ids)

            ana_summary = (await client.get("/api/analytics")).json()
            print(f"\nDashboard Analytics Summary: {ana_summary}")
            assert ana_summary["total_calls"] >= len(created_ids)
            assert ana_summary["evaluated_agent_calls"] < ana_summary["total_calls"]
            assert sum(ana_summary["sentiment_distribution"].values()) == ana_summary["total_calls"]
            assert sum(ana_summary["priority_breakdown"].values()) == ana_summary["total_calls"]
            assert sum(ana_summary["risk_distribution"].values()) == ana_summary["total_calls"]
            assert sum(ana_summary["resolution_breakdown"].values()) == ana_summary["total_calls"]
            assert 0.0 <= ana_summary["avg_satisfaction_score"] <= 10.0
            assert 0.0 <= ana_summary["resolution_rate"] <= 1.0
        finally:
            for cid in created_ids:
                await client.delete(f"/api/calls/{cid}")
