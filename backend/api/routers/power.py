"""api/routers/power.py — Standalone Power Analysis & Sample Size Calculator."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from api.deps import get_current_user

router = APIRouter(prefix="/api/power", tags=["power"])


class PowerRequest(BaseModel):
    test: Literal[
        "independent_t","paired_t","one_sample_t","anova",
        "correlation","chi_square","regression"
    ] = "independent_t"
    effect_size: float = Field(0.5, ge=0.01, le=5.0)
    alpha: float       = Field(0.05, ge=0.001, le=0.20)
    power: float       = Field(0.80, ge=0.50, le=0.999)
    n: Optional[int]   = Field(None, ge=3, le=10000, description="If provided, computes achieved power instead of required n")
    k_groups: int      = Field(3, ge=2, le=20)
    predictors: int    = Field(3, ge=1, le=50)
    df_val: int        = Field(1, ge=1, le=100)


@router.post("/calculate")
def calculate_power(body: PowerRequest, _user=Depends(get_current_user)):
    """
    Standalone power / sample size calculator.
    No job required — accessible to any logged-in user.
    """
    try:
        from analysis.engine.tests.power_analysis import run_sample_size_calculator
        raw_result = run_sample_size_calculator(
            test_type=body.test,
            effect_size=body.effect_size,
            alpha=body.alpha,
            power=body.power,
            n=body.n,
            k_groups=body.k_groups,
            predictors=body.predictors,
            df_val=body.df_val,
        )
        if "error" in raw_result:
            raise HTTPException(status_code=400, detail=raw_result["error"])
        
        # Merge additional_stats if present so both schemas work seamlessly
        stats = raw_result.get("additional_stats") or {}
        if isinstance(stats, dict):
            return {**raw_result, **stats}
        return raw_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/effect-size-guide")
def effect_size_guide(_user=Depends(get_current_user)):
    """Return Cohen's effect size reference tables for all test types."""
    return {
        "cohen_d": {
            "description": "Standardized mean difference (t-tests)",
            "small": 0.2, "medium": 0.5, "large": 0.8,
        },
        "cohen_f": {
            "description": "ANOVA effect size",
            "small": 0.10, "medium": 0.25, "large": 0.40,
        },
        "cohen_f2": {
            "description": "Multiple regression R² change",
            "small": 0.02, "medium": 0.15, "large": 0.35,
        },
        "cohen_w": {
            "description": "Chi-square effect size",
            "small": 0.10, "medium": 0.30, "large": 0.50,
        },
        "pearson_r": {
            "description": "Correlation coefficient",
            "small": 0.10, "medium": 0.30, "large": 0.50,
        },
    }
