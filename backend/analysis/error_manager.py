import logging
import traceback
from typing import Union

logger = logging.getLogger("analysis.pipeline")

def format_user_friendly_error(err: Union[Exception, str, None]) -> str:
    """
    Translates raw technical stack traces, database exceptions, or Python errors
    into clear, human-understandable English messages with helpful guidance.
    """
    if err is None:
        return "The analysis could not complete. Please retry your analysis."
    
    err_str = str(err).lower()
    
    # 1. Database / Session / Serialization / JSON / Flush errors
    if any(kw in err_str for kw in [
        "rollback", "session", "flush", "json serializable", "keys must be str",
        "sqlite", "transaction", "integrityerror", "operationalerror", "datatype", "timestamp"
    ]):
        return (
            "The analysis encountered a data formatting issue while processing your dataset. "
            "Please try running the analysis again. If the issue persists, check that your dataset columns and values are valid."
        )

    # 2. Timeout / Long inactivity
    if any(kw in err_str for kw in ["timeout", "timed out", "inactivity", "took longer", "deadline"]):
        return (
            "The analysis timed out due to a long wait or extended processing time. "
            "Please click Retry to run the analysis again."
        )

    # 3. Missing variables / Column mapping errors
    if any(kw in err_str for kw in ["keyerror", "column", "variable", "not found in dataframe", "not in index", "not found"]):
        return (
            "One or more variables specified in the Research Brief could not be found or processed in the dataset. "
            "Please verify your variable selections in the Research Brief and retry."
        )

    # 4. Empty dataset / File reading errors
    if any(kw in err_str for kw in ["empty", "no rows", "corrupt", "could not parse", "invalid file", "emptydataerror"]):
        return (
            "The uploaded dataset could not be read or contains no valid rows. "
            "Please ensure you uploaded a valid CSV, Excel (.xlsx/.xls), or SPSS (.sav) file."
        )

    # 5. Statistical computation / Degrees of freedom / Sample size errors
    if any(kw in err_str for kw in ["sample size", "degrees of freedom", "singular matrix", "zero division", "division by zero", "zerodivisionerror", "constant"]):
        return (
            "Your dataset has insufficient variation or too few valid observations to calculate one or more statistical tests. "
            "Please check for missing data or constant variables and try again."
        )

    # 6. AI / LLM / Rate limits / Provider outage
    if any(kw in err_str for kw in ["anthropic", "openrouter", "openai", "rate limit", "overloaded", "503", "502", "504", "api key"]):
        return (
            "The AI report generation service is temporarily busy or experiencing high traffic. "
            "Please wait a moment and click Retry."
        )

    # 7. Credit / Billing errors
    if any(kw in err_str for kw in ["credit", "insufficient balance", "payment", "wallet"]):
        return (
            "Insufficient credits to complete this analysis. "
            "Please top up your credit balance in Settings and retry."
        )

    # 8. User rejected decode
    if "rejected by researcher" in err_str or "cancelled during data decoding" in err_str:
        return "The analysis was cancelled during data decoding review."

    # 9. Generic clean fallback
    return (
        "The analysis encountered an unexpected issue and could not complete. "
        "Please click Retry to try again, or check your dataset formatting."
    )
