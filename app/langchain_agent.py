# app/langchain_agent.py
from typing import Any, Dict, List

def call_langchain_agent(patient_name: str, patient_id: int, diagnosis: str, raw_medicines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Minimal stub that matches how your router calls the function:
      llm_result = call_langchain_agent(patient_name, pres.patient_id, pres.diagnosis or "", pres.raw_medicines)

    Returns a dict so your code can do llm_result.get('_meta_model', ...) and assign llm_output safely.
    Replace with your real LangChain/LLM invocation later.
    """
    # Build a simple deterministic output (replace with real LLM call)
    meds_summary = []
    try:
        for m in (raw_medicines or []):
            name = m.get("name") if isinstance(m, dict) else str(m)
            qty = m.get("qty", "") if isinstance(m, dict) else ""
            meds_summary.append(f"{name}{' '+str(qty) if qty else ''}")
    except Exception:
        meds_summary = [str(raw_medicines)]

    result = {
        "_meta_model": "langchain-stub",
        "patient": {"id": patient_id, "name": patient_name},
        "diagnosis": diagnosis or "",
        "medicines": meds_summary,
        "human_readable": f"Prescription for {patient_name} (id:{patient_id}) — diagnosis: {diagnosis}; medicines: {', '.join(meds_summary)}"
    }
    return result
