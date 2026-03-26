import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf


st.set_page_config(
    page_title="SAVR Portföljkollen",
    page_icon="S",
    layout="wide",
)


SAVR_THEME = {
    "brand_red": "#4D4BCC",
    "brand_red_dark": "#3A39EB",
    "ink": "#050505",
    "ink_soft": "#60606C",
    "bg": "#FFFFFF",
    "surface": "#FFFFFF",
    "border": "#E4E4EA",
    "accent_blue": "#667CFF",
    "accent_blue_soft": "#EEF1FF",
    "accent_green": "#4D4BCC",
    "accent_red": "#050505",
}

BRAND_COLORS = [
    SAVR_THEME["accent_blue"],
    "#7A82FB",
    "#ADB4FF",
    "#C9D3E0",
    "#2A405C",
    "#E6EBF2",
]


def format_sek(value: float) -> str:
    return f"{value:,.0f} kr".replace(",", " ")


def format_decimal_sv(value: float, decimals: int = 2, signed: bool = False) -> str:
    numeric_value = round(float(value), decimals)
    template = f"{{:{'+' if signed else ''}.{decimals}f}}"
    formatted = template.format(numeric_value)
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    if formatted in {"-0", "-0.0", "-0.00"}:
        formatted = "0"
    return formatted.replace(".", ",")


def format_pct(value: float) -> str:
    return f"{format_decimal_sv(value)} %"


def format_signed_pct(value: float) -> str:
    formatted = format_decimal_sv(value, signed=True)
    if formatted == "0":
        formatted = "+0"
    return f"{formatted} %"


def format_date_sv(timestamp: pd.Timestamp) -> str:
    month_names = {
        1: "jan",
        2: "feb",
        3: "mar",
        4: "apr",
        5: "maj",
        6: "jun",
        7: "jul",
        8: "aug",
        9: "sep",
        10: "okt",
        11: "nov",
        12: "dec",
    }
    ts = pd.Timestamp(timestamp)
    return f"{ts.day} {month_names[ts.month]} {ts.year}"


def get_category_instrument_catalog() -> dict[str, list[dict]]:
    return {
        "Globalfond": [
            {"ticker": "VT", "name": "Vanguard Total World Stock ETF", "currency": "USD"},
            {"ticker": "ACWI", "name": "iShares MSCI ACWI ETF", "currency": "USD"},
            {"ticker": "URTH", "name": "iShares MSCI World ETF", "currency": "USD"},
        ],
        "Sverigefond": [
            {"ticker": "EWD", "name": "iShares MSCI Sweden ETF", "currency": "USD"},
            {"ticker": "FLSW", "name": "Franklin FTSE Sweden ETF", "currency": "USD"},
        ],
        "Teknikfond": [
            {"ticker": "XLK", "name": "Technology Select Sector SPDR Fund", "currency": "USD"},
            {"ticker": "VGT", "name": "Vanguard Information Technology ETF", "currency": "USD"},
            {"ticker": "IYW", "name": "iShares U.S. Technology ETF", "currency": "USD"},
        ],
        "Tillväxtmarknad": [
            {"ticker": "IEMG", "name": "iShares Core MSCI Emerging Markets ETF", "currency": "USD"},
            {"ticker": "VWO", "name": "Vanguard FTSE Emerging Markets ETF", "currency": "USD"},
            {"ticker": "EEM", "name": "iShares MSCI Emerging Markets ETF", "currency": "USD"},
        ],
        "Småbolagsfond": [
            {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "currency": "USD"},
            {"ticker": "VB", "name": "Vanguard Small-Cap ETF", "currency": "USD"},
            {"ticker": "SCHA", "name": "Schwab U.S. Small-Cap ETF", "currency": "USD"},
        ],
        "Räntefond": [
            {"ticker": "BND", "name": "Vanguard Total Bond Market ETF", "currency": "USD"},
            {"ticker": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF", "currency": "USD"},
            {"ticker": "SCHZ", "name": "Schwab U.S. Aggregate Bond ETF", "currency": "USD"},
        ],
    }


def get_default_category_instrument_map() -> dict[str, str]:
    return {
        category: options[0]["ticker"] for category, options in get_category_instrument_catalog().items()
    }


def get_category_instrument_lookup() -> dict[str, dict]:
    lookup = {}
    for category, options in get_category_instrument_catalog().items():
        for option in options:
            lookup[option["ticker"]] = {**option, "category": category}
    return lookup


def get_portfolio_category_blueprint() -> list[dict]:
    return [
        {
            "category": "Teknikfond",
            "fallback_value_sek": 165000,
            "fallback_last_review_value_sek": 150000,
            "asset_type": "Aktiefond",
            "risk_level": 6.7,
        },
        {
            "category": "Globalfond",
            "fallback_value_sek": 150000,
            "fallback_last_review_value_sek": 147000,
            "asset_type": "Aktiefond",
            "risk_level": 4.1,
        },
        {
            "category": "Sverigefond",
            "fallback_value_sek": 55000,
            "fallback_last_review_value_sek": 56000,
            "asset_type": "Aktiefond",
            "risk_level": 5.1,
        },
        {
            "category": "Tillväxtmarknad",
            "fallback_value_sek": 40000,
            "fallback_last_review_value_sek": 38000,
            "asset_type": "Aktiefond",
            "risk_level": 6.0,
        },
        {
            "category": "Småbolagsfond",
            "fallback_value_sek": 30000,
            "fallback_last_review_value_sek": 28000,
            "asset_type": "Aktiefond",
            "risk_level": 6.3,
        },
        {
            "category": "Räntefond",
            "fallback_value_sek": 20000,
            "fallback_last_review_value_sek": 22000,
            "asset_type": "Räntefond",
            "risk_level": 1.8,
        },
    ]


def get_category_instrument_label(ticker: str) -> str:
    instrument = get_category_instrument_lookup().get(ticker)
    if instrument is None:
        return ticker
    return f"{instrument['name']} ({ticker})"


def get_active_category_instrument_map(selected_profile: str, category_order: list[str]) -> dict[str, str]:
    default_map = get_default_category_instrument_map()
    lookup = get_category_instrument_lookup()
    if selected_profile != "Egen profil":
        return dict(default_map)

    active_map = {}
    for category in category_order:
        state_key = f"category_instrument_{category}"
        candidate = st.session_state.get(state_key, default_map[category])
        instrument = lookup.get(candidate)
        if instrument is None or instrument["category"] != category:
            candidate = default_map[category]
        active_map[category] = candidate
    return active_map


def load_live_portfolio_template(selected_instruments: dict[str, str] | None = None) -> pd.DataFrame:
    selected_instruments = selected_instruments or get_default_category_instrument_map()
    instrument_lookup = get_category_instrument_lookup()
    default_map = get_default_category_instrument_map()
    data = []
    for blueprint in get_portfolio_category_blueprint():
        category = blueprint["category"]
        ticker = selected_instruments.get(category, default_map[category])
        instrument = instrument_lookup.get(ticker, instrument_lookup[default_map[category]])
        data.append(
            {
                "name": instrument["name"],
                "ticker": instrument["ticker"],
                "units": np.nan,
                "currency": instrument["currency"],
                "fallback_value_sek": blueprint["fallback_value_sek"],
                "fallback_last_review_value_sek": blueprint["fallback_last_review_value_sek"],
                "category": category,
                "asset_type": blueprint["asset_type"],
                "risk_level": blueprint["risk_level"],
            }
        )
    return pd.DataFrame(data)


def load_live_watchlist_template() -> pd.DataFrame:
    data = [
        {
            "company_name": "Apple",
            "ticker": "AAPL",
            "units": 22,
            "currency": "USD",
            "sector": "Teknik",
            "fallback_position_value_sek": 45500,
        },
        {
            "company_name": "Microsoft",
            "ticker": "MSFT",
            "units": 12,
            "currency": "USD",
            "sector": "Teknik",
            "fallback_position_value_sek": 38200,
        },
        {
            "company_name": "NVIDIA",
            "ticker": "NVDA",
            "units": 32,
            "currency": "USD",
            "sector": "Halvledare",
            "fallback_position_value_sek": 52100,
        },
        {
            "company_name": "Investor B",
            "ticker": "INVE-B.ST",
            "units": 120,
            "currency": "SEK",
            "sector": "Investmentbolag",
            "fallback_position_value_sek": 28400,
        },
        {
            "company_name": "Volvo B",
            "ticker": "VOLV-B.ST",
            "units": 85,
            "currency": "SEK",
            "sector": "Industri",
            "fallback_position_value_sek": 21600,
        },
    ]
    return pd.DataFrame(data)


def get_currency_fx_ticker(currency: str) -> str | None:
    currency = str(currency).upper()
    if currency == "SEK":
        return None
    return f"{currency}SEK=X"


def get_fx_tickers(currencies: list[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                fx_ticker
                for currency in currencies
                if (fx_ticker := get_currency_fx_ticker(currency)) is not None
            }
        )
    )


def get_latest_series_value(series: pd.Series, fallback: float = np.nan) -> float:
    clean = series.dropna()
    if clean.empty:
        return float(fallback)
    return float(clean.iloc[-1])


def get_reference_series_value(series: pd.Series, trading_days: int, fallback: float = np.nan) -> float:
    clean = series.dropna()
    if clean.empty:
        return float(fallback)
    if len(clean) <= trading_days:
        return float(clean.iloc[0])
    return float(clean.iloc[-(trading_days + 1)])


def convert_market_value_to_sek(
    units: float,
    price_series: pd.Series,
    fx_series: pd.Series | None,
    fallback_current: float,
    fallback_reference: float,
    reference_days: int = 21,
) -> tuple[float, float]:
    current_price = get_latest_series_value(price_series, np.nan)
    reference_price = get_reference_series_value(price_series, reference_days, np.nan)
    current_fx = 1.0 if fx_series is None else get_latest_series_value(fx_series, np.nan)
    reference_fx = (
        1.0 if fx_series is None else get_reference_series_value(fx_series, reference_days, np.nan)
    )
    if np.isnan(current_price) or np.isnan(current_fx):
        return float(fallback_current), float(fallback_reference)
    if np.isnan(reference_price) or np.isnan(reference_fx):
        reference_value = float(fallback_reference)
    else:
        reference_value = float(units * reference_price * reference_fx)
    current_value = float(units * current_price * current_fx)
    return current_value, reference_value


def derive_units_from_fallback_values(
    price_series: pd.Series,
    fx_series: pd.Series | None,
    fallback_current: float,
    fallback_reference: float,
    reference_days: int = 21,
) -> float:
    current_price = get_latest_series_value(price_series, np.nan)
    reference_price = get_reference_series_value(price_series, reference_days, np.nan)
    current_fx = 1.0 if fx_series is None else get_latest_series_value(fx_series, np.nan)
    reference_fx = (
        1.0 if fx_series is None else get_reference_series_value(fx_series, reference_days, np.nan)
    )

    if not np.isnan(reference_price) and not np.isnan(reference_fx):
        reference_denominator = reference_price * reference_fx
        if reference_denominator:
            return float(fallback_reference / reference_denominator)

    if not np.isnan(current_price) and not np.isnan(current_fx):
        current_denominator = current_price * current_fx
        if current_denominator:
            return float(fallback_current / current_denominator)

    return np.nan


def build_live_portfolio_values(portfolio_template: pd.DataFrame, price_history: pd.DataFrame) -> pd.DataFrame:
    portfolio = portfolio_template.copy()
    current_values = []
    reference_values = []
    data_sources = []
    resolved_units = []
    for _, row in portfolio.iterrows():
        price_series = price_history[row["ticker"]] if row["ticker"] in price_history.columns else pd.Series(dtype=float)
        fx_ticker = get_currency_fx_ticker(row["currency"])
        fx_series = price_history[fx_ticker] if fx_ticker and fx_ticker in price_history.columns else None
        units = float(row["units"]) if pd.notna(row["units"]) else np.nan
        if np.isnan(units) or units <= 0:
            units = derive_units_from_fallback_values(
                price_series=price_series,
                fx_series=fx_series,
                fallback_current=float(row["fallback_value_sek"]),
                fallback_reference=float(row["fallback_last_review_value_sek"]),
            )
        if np.isnan(units) or units <= 0:
            current_value = float(row["fallback_value_sek"])
            reference_value = float(row["fallback_last_review_value_sek"])
        else:
            current_value, reference_value = convert_market_value_to_sek(
                units=units,
                price_series=price_series,
                fx_series=fx_series,
                fallback_current=float(row["fallback_value_sek"]),
                fallback_reference=float(row["fallback_last_review_value_sek"]),
            )
        current_values.append(current_value)
        reference_values.append(reference_value)
        data_sources.append("Marknadsdata" if not price_series.dropna().empty else "Beräknat värde")
        resolved_units.append(units if not np.isnan(units) else 0.0)
    portfolio["value_sek"] = current_values
    portfolio["last_review_value_sek"] = reference_values
    portfolio["data_source"] = data_sources
    portfolio["units"] = resolved_units
    return portfolio


def build_live_watchlist_values(watchlist_template: pd.DataFrame, price_history: pd.DataFrame) -> pd.DataFrame:
    watchlist = watchlist_template.copy()
    position_values = []
    current_prices = []
    data_sources = []
    for _, row in watchlist.iterrows():
        price_series = price_history[row["ticker"]] if row["ticker"] in price_history.columns else pd.Series(dtype=float)
        fx_ticker = get_currency_fx_ticker(row["currency"])
        fx_series = price_history[fx_ticker] if fx_ticker and fx_ticker in price_history.columns else None
        current_value, _ = convert_market_value_to_sek(
            units=float(row["units"]),
            price_series=price_series,
            fx_series=fx_series,
            fallback_current=float(row["fallback_position_value_sek"]),
            fallback_reference=float(row["fallback_position_value_sek"]),
        )
        current_prices.append(get_latest_series_value(price_series, np.nan))
        position_values.append(current_value)
        data_sources.append("Marknadsdata" if not price_series.dropna().empty else "Beräknat värde")
    watchlist["position_value_sek"] = position_values
    watchlist["latest_market_price"] = current_prices
    watchlist["data_source"] = data_sources
    return watchlist


def build_yfinance_instrument_universe(
    portfolio: pd.DataFrame, watchlist: pd.DataFrame
) -> pd.DataFrame:
    portfolio_view = portfolio[
        ["name", "ticker", "category", "value_sek", "data_source"]
    ].copy()
    portfolio_view = portfolio_view.rename(
        columns={
            "name": "company_name",
            "category": "sector",
            "value_sek": "position_value_sek",
        }
    )
    portfolio_view["instrument_type"] = "Fond/ETF"

    watchlist_view = watchlist[
        ["company_name", "ticker", "sector", "position_value_sek", "data_source"]
    ].copy()
    watchlist_view["instrument_type"] = "Aktie"

    combined = pd.concat([watchlist_view, portfolio_view], ignore_index=True)
    combined = combined.drop_duplicates(subset=["ticker"]).sort_values(
        ["instrument_type", "company_name"], ascending=[True, True]
    )
    return combined.reset_index(drop=True)


def map_volatility_to_risk_level(volatility_pct: float) -> float:
    if pd.isna(volatility_pct):
        return np.nan
    buckets = [4, 8, 12, 18, 24, 30]
    for index, threshold in enumerate(buckets, start=1):
        if volatility_pct <= threshold:
            return float(index)
    return 7.0


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_savr_public_fund_catalog() -> pd.DataFrame:
    url = "https://strapi.savr.com/api/funds?pagination[pageSize]=1000&sort=id"
    response = requests.get(
        url,
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json().get("data", [])
    if not payload:
        return pd.DataFrame(columns=["id", "isin", "currency"])
    df = pd.DataFrame(payload)
    isin_split = df["isin_and_currency"].fillna("").str.split(".", n=1, expand=True)
    df["isin"] = isin_split[0].fillna("")
    df["currency"] = isin_split[1].fillna("")
    return df[["id", "isin", "currency"]]


def get_risk_profiles() -> dict:
    return {
        "Försiktig": {
            "description": "Lägre svängningar, högre andel räntor och fokus på stabilitet.",
            "risk_appetite": 3,
            "equity_target": 50,
            "max_single_holding": 30,
            "min_portfolio_sharpe": 0.65,
            "max_portfolio_volatility": 12.0,
            "max_drawdown_tolerance": 16.0,
            "equity_buffer": 2,
            "category_gap_threshold": 4,
            "top_three_threshold": 65,
            "minimum_trade_size": 1000,
            "target_weights": {
                "Globalfond": 25,
                "Sverigefond": 10,
                "Teknikfond": 5,
                "Tillväxtmarknad": 5,
                "Småbolagsfond": 5,
                "Räntefond": 50,
            },
        },
        "Balanserad": {
            "description": "En jämn mix av tillväxt och trygghet, med bred aktiespridning.",
            "risk_appetite": 6,
            "equity_target": 80,
            "max_single_holding": 35,
            "min_portfolio_sharpe": 0.50,
            "max_portfolio_volatility": 18.0,
            "max_drawdown_tolerance": 27.0,
            "equity_buffer": 5,
            "category_gap_threshold": 7,
            "top_three_threshold": 75,
            "minimum_trade_size": 1000,
            "target_weights": {
                "Globalfond": 35,
                "Sverigefond": 15,
                "Teknikfond": 10,
                "Tillväxtmarknad": 10,
                "Småbolagsfond": 10,
                "Räntefond": 20,
            },
        },
        "Aggressiv": {
            "description": "Hög tillväxtambition med större aktieandel och plats för tematiska innehav.",
            "risk_appetite": 8,
            "equity_target": 90,
            "max_single_holding": 40,
            "min_portfolio_sharpe": 0.35,
            "max_portfolio_volatility": 26.0,
            "max_drawdown_tolerance": 40.0,
            "equity_buffer": 8,
            "category_gap_threshold": 10,
            "top_three_threshold": 85,
            "minimum_trade_size": 1500,
            "target_weights": {
                "Globalfond": 35,
                "Sverigefond": 15,
                "Teknikfond": 15,
                "Tillväxtmarknad": 15,
                "Småbolagsfond": 10,
                "Räntefond": 10,
            },
        },
    }


def get_notification_intervals() -> dict:
    return {
        "Veckovis": {
            "reference_text": "förra veckan",
            "offset": pd.DateOffset(weeks=1),
            "trading_days": 5,
        },
        "Månadsvis": {
            "reference_text": "förra månaden",
            "offset": pd.DateOffset(months=1),
            "trading_days": 21,
        },
        "Kvartalsvis": {
            "reference_text": "förra kvartalet",
            "offset": pd.DateOffset(months=3),
            "trading_days": 63,
        },
        "Var 6:e månad": {
            "reference_text": "för sex månader sedan",
            "offset": pd.DateOffset(months=6),
            "trading_days": 126,
        },
        "Årligen": {
            "reference_text": "för ett år sedan",
            "offset": pd.DateOffset(years=1),
            "trading_days": 252,
        },
    }


def get_mock_backtest_intervals() -> dict:
    return {
        "1 vecka bakåt": {
            "reference_text": "för 1 vecka sedan",
            "trading_days": 5,
        },
        "1 månad bakåt": {
            "reference_text": "för 1 månad sedan",
            "trading_days": 21,
        },
        "1 kvartal bakåt": {
            "reference_text": "för 1 kvartal sedan",
            "trading_days": 63,
        },
        "6 månader bakåt": {
            "reference_text": "för 6 månader sedan",
            "trading_days": 126,
        },
        "1 år bakåt": {
            "reference_text": "för 1 år sedan",
            "trading_days": 252,
        },
    }


def get_mock_future_horizons() -> dict:
    return {
        "1 månad framåt": {
            "label": "nästa månad",
            "trading_days": 21,
        },
        "3 månader framåt": {
            "label": "nästa kvartal",
            "trading_days": 63,
        },
        "6 månader framåt": {
            "label": "kommande 6 månader",
            "trading_days": 126,
        },
    }


def get_mock_rebalance_modes() -> dict:
    return {
        "Buy and hold": {
            "period_code": None,
            "short_label": "buy and hold",
            "description": "Startvikterna sätts en gång och får sedan driva fritt med marknaden.",
        },
        "Månadsvis rebalansering": {
            "period_code": "M",
            "short_label": "månadsvis rebalansering",
            "description": "Portföljen återställs mot målvikterna vid slutet av varje månad.",
        },
        "Kvartalsvis rebalansering": {
            "period_code": "Q",
            "short_label": "kvartalsvis rebalansering",
            "description": "Portföljen återställs mot målvikterna vid slutet av varje kvartal.",
        },
    }


def get_analysis_windows() -> dict:
    return {
        "1 år": {"trading_days": 252},
        "3 år": {"trading_days": 756},
        "5 år": {"trading_days": 1260},
    }


def get_risk_preference_defaults(risk_appetite: int) -> dict:
    return {
        "max_portfolio_volatility": round(6 + risk_appetite * 2.2, 1),
        "min_portfolio_sharpe": round(0.8 - risk_appetite * 0.05, 2),
        "max_drawdown_tolerance": round(6 + risk_appetite * 3.5, 1),
    }


def apply_profile_defaults(profile_name: str) -> None:
    if profile_name == "Egen profil":
        st.session_state.selected_profile = "Egen profil"
        return
    base_profile = get_risk_profiles()[profile_name]
    default_instruments = get_default_category_instrument_map()
    current_profile_name = str(st.session_state.get("profile_name", "")).strip()
    default_profile_names = {f"{name} profil" for name in get_risk_profiles()} | {"Min profil"}
    st.session_state.selected_profile = profile_name
    if not current_profile_name or current_profile_name in default_profile_names:
        st.session_state.profile_name = f"{profile_name} profil"
    st.session_state.risk_appetite = int(base_profile["risk_appetite"])
    st.session_state.concentration_threshold = base_profile["max_single_holding"]
    st.session_state.equity_buffer = int(base_profile["equity_buffer"])
    st.session_state.category_gap_threshold = int(base_profile["category_gap_threshold"])
    st.session_state.top_three_threshold = int(base_profile["top_three_threshold"])
    st.session_state.minimum_trade_size = int(base_profile["minimum_trade_size"])
    st.session_state.min_portfolio_sharpe = float(base_profile["min_portfolio_sharpe"])
    st.session_state.max_portfolio_volatility = float(base_profile["max_portfolio_volatility"])
    st.session_state.max_drawdown_tolerance = float(base_profile["max_drawdown_tolerance"])
    for category, weight in base_profile["target_weights"].items():
        st.session_state[f"target_weight_{category}"] = float(weight)
    for category, ticker in default_instruments.items():
        st.session_state[f"category_instrument_{category}"] = ticker


def handle_profile_selection_change() -> None:
    apply_profile_defaults(st.session_state.selected_profile)


def apply_recommended_risk_targets(risk_appetite: int) -> None:
    recommended = get_risk_preference_defaults(risk_appetite)
    st.session_state.min_portfolio_sharpe = float(recommended["min_portfolio_sharpe"])
    st.session_state.max_portfolio_volatility = float(recommended["max_portfolio_volatility"])
    st.session_state.max_drawdown_tolerance = float(recommended["max_drawdown_tolerance"])


def parse_sv_date_input(date_text: str) -> pd.Timestamp | None:
    cleaned = "".join(character for character in date_text.strip() if character.isdigit())
    if len(cleaned) != 8:
        return None
    try:
        return pd.to_datetime(cleaned, format="%d%m%Y").normalize()
    except ValueError:
        return None


def resolve_input_date(calendar_value, manual_text: str) -> tuple[pd.Timestamp | None, bool]:
    manual_text = manual_text.strip()
    if manual_text:
        parsed = parse_sv_date_input(manual_text)
        if parsed is not None:
            return parsed, True
        if calendar_value is None:
            return None, False
        return pd.Timestamp(calendar_value).normalize(), False
    if calendar_value is None:
        return None, True
    return pd.Timestamp(calendar_value).normalize(), True


def get_risk_questionnaire() -> list[dict]:
    return [
        {
            "key": "risk_q_horizon",
            "question": "När tror du att pengarna kan behövas?",
            "weight": 25,
            "options": [
                {"label": "Inom 1-2 år", "score": 0.10},
                {"label": "Om 3-5 år", "score": 0.40},
                {"label": "Om 5-10 år", "score": 0.70},
                {"label": "Om mer än 10 år", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_drawdown",
            "question": "Hur skulle du sannolikt reagera om portföljen faller 20 %?",
            "weight": 30,
            "options": [
                {"label": "Säljer för att minska risken", "score": 0.05},
                {"label": "Minskar lite och avvaktar", "score": 0.35},
                {"label": "Behåller och väntar ut", "score": 0.70},
                {"label": "Ökar om läget känns rätt", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_goal",
            "question": "Vilket mål är viktigast med sparandet?",
            "weight": 15,
            "options": [
                {"label": "Skydda kapitalet", "score": 0.10},
                {"label": "Jämn balans mellan trygghet och tillväxt", "score": 0.55},
                {"label": "Hög långsiktig tillväxt", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_experience",
            "question": "Hur van är du vid fonder, aktier och marknadssvängningar?",
            "weight": 15,
            "options": [
                {"label": "Ny inom sparande", "score": 0.15},
                {"label": "Lite erfarenhet", "score": 0.45},
                {"label": "God erfarenhet", "score": 0.75},
                {"label": "Mycket erfarenhet", "score": 1.00},
            ],
        },
        {
            "key": "risk_q_liquidity",
            "question": "Hur stort är behovet av att kunna använda pengarna snabbt?",
            "weight": 15,
            "options": [
                {"label": "Stort behov av snabb tillgång", "score": 0.10},
                {"label": "Viss flexibilitet behövs", "score": 0.40},
                {"label": "Litet behov på kort sikt", "score": 0.75},
                {"label": "Nästan inget behov alls", "score": 1.00},
            ],
        },
    ]


def calculate_risk_questionnaire_profile() -> dict:
    total_weighted_score = 0.0
    answers = []
    for question in get_risk_questionnaire():
        selected_label = st.session_state.get(
            question["key"], question["options"][0]["label"]
        )
        selected_option = next(
            option for option in question["options"] if option["label"] == selected_label
        )
        weighted_score = question["weight"] * selected_option["score"]
        total_weighted_score += weighted_score
        answers.append(
            {
                "question": question["question"],
                "answer": selected_label,
                "weight": question["weight"],
                "score": selected_option["score"],
                "weighted_score": weighted_score,
            }
        )

    risk_level = max(1, min(10, int(round(total_weighted_score / 10))))
    return {
        "risk_level": risk_level,
        "score_100": total_weighted_score,
        "answers": answers,
    }


def apply_questionnaire_risk_profile() -> None:
    result = calculate_risk_questionnaire_profile()
    st.session_state.selected_profile = "Egen profil"
    st.session_state.risk_appetite = result["risk_level"]
    apply_recommended_risk_targets(result["risk_level"])


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_history(tickers: tuple[str, ...], period: str = "5y") -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()

    data = yf.download(
        tickers=list(tickers),
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if data.empty:
        return pd.DataFrame()

    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data.to_frame(name=tickers[0])
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    close = close.sort_index().ffill().dropna(how="all")
    close.columns = [str(column) for column in close.columns]
    return close


def ensure_price_history_for_tickers(
    price_history: pd.DataFrame, tickers: list[str], period: str = "5y"
) -> pd.DataFrame:
    requested_tickers = list(dict.fromkeys(tickers))
    if not requested_tickers:
        return pd.DataFrame()

    missing_tickers = [
        ticker
        for ticker in requested_tickers
        if ticker not in price_history.columns or price_history[ticker].dropna().empty
    ]
    if not missing_tickers:
        return price_history[requested_tickers].copy()

    refreshed_history = fetch_price_history(tuple(missing_tickers), period=period)
    combined_history = pd.concat([price_history, refreshed_history], axis=1)
    combined_history = combined_history.loc[:, ~combined_history.columns.duplicated(keep="last")]
    available_tickers = [ticker for ticker in requested_tickers if ticker in combined_history.columns]
    if not available_tickers:
        return pd.DataFrame()
    return combined_history[available_tickers].copy()


def slice_price_history(prices: pd.DataFrame, trading_days: int) -> pd.DataFrame:
    if prices.empty:
        return prices
    if len(prices) <= trading_days:
        return prices.dropna(how="all")
    return prices.iloc[-trading_days:].dropna(how="all")


def get_interval_price(series: pd.Series, trading_days: int) -> float:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    if len(clean) <= trading_days:
        return float(clean.iloc[0])
    return float(clean.iloc[-(trading_days + 1)])


def calculate_drawdown(return_series: pd.Series) -> float:
    if return_series.empty:
        return 0.0
    cumulative = (1 + return_series).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    return float(drawdown.min() * 100)


def compute_historical_metrics(
    price_history: pd.DataFrame,
    weights: dict,
    risk_free_rate_pct: float,
) -> tuple[pd.DataFrame, dict]:
    if price_history.empty:
        empty_cols = [
            "ticker",
            "annual_return_pct",
            "annual_volatility_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "trailing_1m_pct",
        ]
        return pd.DataFrame(columns=empty_cols), {
            "annual_return_pct": 0.0,
            "annual_volatility_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
        }

    returns = price_history.pct_change().dropna(how="all")
    annual_return = returns.mean() * 252 * 100
    annual_vol = returns.std() * np.sqrt(252) * 100
    risk_free_rate = risk_free_rate_pct
    sharpe = (annual_return - risk_free_rate) / annual_vol.replace(0, np.nan)
    max_drawdown = returns.apply(calculate_drawdown)
    trailing_1m = price_history.apply(
        lambda series: (series.dropna().iloc[-1] / get_interval_price(series, 21) - 1) * 100
        if not series.dropna().empty
        else 0.0
    )

    asset_metrics = pd.DataFrame(
        {
            "ticker": annual_return.index,
            "annual_return_pct": annual_return.values,
            "annual_volatility_pct": annual_vol.values,
            "sharpe_ratio": sharpe.fillna(0).values,
            "max_drawdown_pct": max_drawdown.values,
            "trailing_1m_pct": trailing_1m.values,
        }
    )

    usable_tickers = [ticker for ticker in weights if ticker in returns.columns]
    if not usable_tickers:
        portfolio_summary = {
            "annual_return_pct": 0.0,
            "annual_volatility_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
        }
        return asset_metrics, portfolio_summary

    normalized_weights = pd.Series(weights, dtype=float)
    normalized_weights = normalized_weights[usable_tickers]
    normalized_weights = normalized_weights / normalized_weights.sum()
    portfolio_returns = returns[usable_tickers].mul(normalized_weights, axis=1).sum(axis=1)
    portfolio_annual_return = float(portfolio_returns.mean() * 252 * 100)
    portfolio_annual_vol = float(portfolio_returns.std() * np.sqrt(252) * 100)
    portfolio_sharpe = (
        (portfolio_annual_return - risk_free_rate) / portfolio_annual_vol
        if portfolio_annual_vol
        else 0.0
    )
    portfolio_max_drawdown = calculate_drawdown(portfolio_returns)

    portfolio_summary = {
        "annual_return_pct": portfolio_annual_return,
        "annual_volatility_pct": portfolio_annual_vol,
        "sharpe_ratio": portfolio_sharpe,
        "max_drawdown_pct": portfolio_max_drawdown,
    }
    return asset_metrics, portfolio_summary


def build_market_chip_label(price_history: pd.DataFrame, ticker: str, label: str) -> str:
    if ticker not in price_history.columns or price_history[ticker].dropna().empty:
        return f"{label} <strong>--</strong>"

    series = price_history[ticker].dropna()
    if len(series) < 2:
        return f"{label} <strong>--</strong>"

    change_pct = (series.iloc[-1] / series.iloc[-2] - 1) * 100
    return f"{label} <strong>{format_signed_pct(change_pct)}</strong>"


def normalize_target_weights(raw_weights: dict) -> tuple[dict, float]:
    total = float(sum(raw_weights.values()))
    if total <= 0:
        equal_weight = 100 / len(raw_weights)
        return {category: equal_weight for category in raw_weights}, total

    normalized = {
        category: (weight / total) * 100 for category, weight in raw_weights.items()
    }
    return normalized, total


def build_personal_profile(profile_name: str, raw_weights: dict, max_single_holding: int) -> dict:
    normalized_weights, raw_total = normalize_target_weights(raw_weights)
    equity_target = sum(
        weight for category, weight in normalized_weights.items() if category != "Räntefond"
    )
    return {
        "description": "Personlig målprofil baserad på egna viktmål och egna varningsgränser.",
        "equity_target": equity_target,
        "max_single_holding": max_single_holding,
        "target_weights": normalized_weights,
        "raw_weight_total": raw_total,
        "profile_name": profile_name,
    }


def prepare_portfolio(
    portfolio: pd.DataFrame, profile: dict, asset_market_metrics: pd.DataFrame | None = None
) -> pd.DataFrame:
    df = portfolio.copy()
    total_value = df["value_sek"].sum()
    previous_total = df["last_review_value_sek"].sum()

    # Koppla varje innehav till en enkel målportfölj så att vi kan räkna ut gap i både vikt och kronor.
    df["current_weight"] = df["value_sek"] / total_value
    df["current_weight_pct"] = df["current_weight"] * 100
    df["last_review_weight_pct"] = df["last_review_value_sek"] / previous_total * 100
    df["weight_change_since_review_pct"] = (
        df["current_weight_pct"] - df["last_review_weight_pct"]
    )
    df["value_change_since_review_pct"] = (
        (df["value_sek"] / df["last_review_value_sek"]) - 1
    ) * 100
    df["target_weight_pct"] = df["category"].map(profile["target_weights"]).fillna(0)
    df["target_weight"] = df["target_weight_pct"] / 100
    df["target_value"] = total_value * df["target_weight"]
    df["trade_value"] = df["target_value"] - df["value_sek"]
    df["weight_gap_pct"] = df["target_weight_pct"] - df["current_weight_pct"]
    df["risk_contribution"] = df["current_weight"] * df["risk_level"]
    df["trade_action"] = df["trade_value"].apply(
        lambda x: "Köp" if x > 0 else ("Sälj" if x < 0 else "Behåll")
    )

    if asset_market_metrics is not None and not asset_market_metrics.empty:
        df = df.merge(asset_market_metrics, how="left", on="ticker")
    else:
        df["annual_return_pct"] = np.nan
        df["annual_volatility_pct"] = np.nan
        df["sharpe_ratio"] = np.nan
        df["max_drawdown_pct"] = np.nan
        df["trailing_1m_pct"] = np.nan

    df["annual_return_pct"] = df["annual_return_pct"].fillna(0.0)
    df["annual_volatility_pct"] = df["annual_volatility_pct"].fillna(0.0)
    df["sharpe_ratio"] = df["sharpe_ratio"].fillna(0.0)
    df["max_drawdown_pct"] = df["max_drawdown_pct"].fillna(0.0)
    df["trailing_1m_pct"] = df["trailing_1m_pct"].fillna(0.0)
    df["risk_level"] = df["annual_volatility_pct"].apply(map_volatility_to_risk_level).fillna(df["risk_level"])
    df["risk_contribution"] = df["current_weight"] * df["risk_level"]
    df["weighted_sharpe_contribution"] = df["current_weight"] * df["sharpe_ratio"]
    return df


def calculate_metrics(df: pd.DataFrame, profile: dict, market_summary: dict) -> dict:
    total_value = df["value_sek"].sum()
    largest = df.sort_values("current_weight_pct", ascending=False).iloc[0]
    equity_exposure = (
        df.loc[df["asset_type"] == "Aktiefond", "value_sek"].sum() / total_value * 100
    )
    portfolio_risk = (df["current_weight"] * df["risk_level"]).sum()
    risk_score = round(portfolio_risk / 7 * 100)
    hhi = round((df["current_weight"] ** 2).sum() * 10000)
    target_risk = round(
        (
            df["target_weight"]
            * df["risk_level"]
        ).sum()
        / 7
        * 100
    )
    top_three_share = (
        df.sort_values("current_weight_pct", ascending=False)
        .head(3)["current_weight_pct"]
        .sum()
    )
    return {
        "total_value": total_value,
        "largest_name": largest["name"],
        "largest_weight_pct": largest["current_weight_pct"],
        "equity_exposure": equity_exposure,
        "risk_score": risk_score,
        "target_risk_score": target_risk,
        "hhi": hhi,
        "top_three_share": top_three_share,
        "equity_gap": equity_exposure - profile["equity_target"],
        "portfolio_sharpe": market_summary["sharpe_ratio"],
        "portfolio_volatility_pct": market_summary["annual_volatility_pct"],
        "portfolio_return_pct": market_summary["annual_return_pct"],
        "portfolio_max_drawdown_pct": market_summary["max_drawdown_pct"],
    }


def detect_imbalances(
    df: pd.DataFrame, profile_name: str, profile: dict, settings: dict
) -> list:
    metrics = calculate_metrics(df, profile, settings["market_summary"])
    insights = []
    threshold = settings["concentration_threshold"]
    equity_buffer = settings["equity_buffer"]
    category_gap_threshold = settings["category_gap_threshold"]
    min_portfolio_sharpe = settings["min_portfolio_sharpe"]
    max_portfolio_volatility = settings["max_portfolio_volatility"]
    max_drawdown_tolerance = settings["max_drawdown_tolerance"]

    largest = df.sort_values("current_weight_pct", ascending=False).iloc[0]
    if largest["current_weight_pct"] > threshold:
        insights.append(
            {
                "tone": "warning",
                "title": f"Din valda gräns för {largest['name']} är passerad",
                "body": (
                    f"Innehavet står för {format_pct(largest['current_weight_pct'])} av portföljen. "
                    f"Det är över din egen gräns på {threshold} %. Om du vill följa din profil "
                    "kan det vara ett bra tillfälle att se över vikten."
                ),
            }
        )

    if metrics["equity_gap"] > equity_buffer:
        insights.append(
            {
                "tone": "warning",
                "title": "Aktieandelen ligger över din valda profil",
                "body": (
                    f"Portföljen ligger på {format_pct(metrics['equity_exposure'])} aktier, "
                    f"medan profilen {profile_name} är satt till cirka {format_pct(profile['equity_target'])}."
                ),
            }
        )

    if metrics["portfolio_sharpe"] < min_portfolio_sharpe:
        insights.append(
            {
                "tone": "warning",
                "title": "Den historiska Sharpekvoten är under din målnivå",
                "body": (
                    f"Portföljens historiska Sharpe är {format_decimal_sv(metrics['portfolio_sharpe'])} "
                    f"mot ditt mål på {format_decimal_sv(min_portfolio_sharpe)}."
                ),
            }
        )

    if metrics["portfolio_volatility_pct"] > max_portfolio_volatility:
        insights.append(
            {
                "tone": "warning",
                "title": "Portföljen svänger mer än din valda risknivå tillåter",
                "body": (
                    f"Historisk volatilitet är {format_pct(metrics['portfolio_volatility_pct'])}, "
                    f"vilket är över ditt tak på {format_pct(max_portfolio_volatility)}."
                ),
            }
        )

    if abs(metrics["portfolio_max_drawdown_pct"]) > max_drawdown_tolerance:
        insights.append(
            {
                "tone": "warning",
                "title": "Historisk nedgång är högre än din tolerans",
                "body": (
                    f"Portföljens största historiska fall är {format_pct(abs(metrics['portfolio_max_drawdown_pct']))}, "
                    f"mot din gräns på {format_pct(max_drawdown_tolerance)}."
                ),
            }
        )

    overweight = df.sort_values("weight_gap_pct").iloc[0]
    if overweight["weight_gap_pct"] < -category_gap_threshold:
        insights.append(
            {
                "tone": "warning",
                "title": f"Din målvikt för {overweight['category']} överskrids",
                "body": (
                    f"Nuvarande vikt är {format_pct(overweight['current_weight_pct'])}, "
                    f"medan din målvikt är {format_pct(overweight['target_weight_pct'])}. "
                    "Portföljen avviker därmed från den fördelning du har valt."
                ),
            }
        )

    underweight = df.sort_values("weight_gap_pct", ascending=False).iloc[0]
    if underweight["weight_gap_pct"] > category_gap_threshold:
        insights.append(
            {
                "tone": "info",
                "title": f"Din målvikt för {underweight['category']} underskrids",
                "body": (
                    f"Nuvarande vikt är {format_pct(underweight['current_weight_pct'])}, "
                    f"medan din målvikt är {format_pct(underweight['target_weight_pct'])}. "
                    "Det innebär att portföljen just nu ligger under din valda fördelning."
                ),
            }
        )

    weak_sharpe = df.sort_values("sharpe_ratio").iloc[0]
    if weak_sharpe["sharpe_ratio"] < min_portfolio_sharpe and weak_sharpe["current_weight_pct"] > 8:
        insights.append(
            {
                "tone": "info",
                "title": f"{weak_sharpe['name']} ligger under dina riskmål historiskt",
                "body": (
                    f"Innehavet har en historisk Sharpe på {format_decimal_sv(weak_sharpe['sharpe_ratio'])} "
                    f"och väger {format_pct(weak_sharpe['current_weight_pct'])} i portföljen."
                ),
            }
        )

    if not insights:
        insights.append(
            {
                "tone": "success",
                "title": "Portföljen ligger nära dina valda nivåer",
                "body": "Nuvarande fördelning ligger nära dina mål och de historiska riskmåtten håller sig inom dina valda ramar.",
            }
        )

    return insights


def build_trade_plan(df: pd.DataFrame, minimum_trade_size: int) -> pd.DataFrame:
    plan = df.copy()
    plan["trade_amount"] = plan["trade_value"].abs()
    plan = plan.loc[plan["trade_amount"] >= minimum_trade_size].copy()
    plan["action_text"] = plan.apply(
        lambda row: f"{row['trade_action']} {format_sek(row['trade_amount'])}", axis=1
    )
    return plan.sort_values("trade_amount", ascending=False)


def build_mock_allocation(
    watchlist: pd.DataFrame, selected_assets: list, fake_amount: int, raw_weights: dict
) -> tuple[pd.DataFrame, dict]:
    if not selected_assets:
        return pd.DataFrame(), {"raw_weight_total": 0.0, "fake_amount": fake_amount}

    weights, raw_total = normalize_target_weights(
        {asset: raw_weights.get(asset, 0.0) for asset in selected_assets}
    )
    df = watchlist.loc[watchlist["company_name"].isin(selected_assets)].copy()
    df["allocation_pct"] = df["company_name"].map(weights)
    df["investment_amount"] = fake_amount * df["allocation_pct"] / 100
    return df, {"raw_weight_total": raw_total, "fake_amount": fake_amount}


def get_rebalance_dates(index: pd.DatetimeIndex, rebalance_mode: str) -> set[pd.Timestamp]:
    period_code = get_mock_rebalance_modes()[rebalance_mode]["period_code"]
    if period_code is None or len(index) < 3:
        return set()

    grouped_period_ends = index.to_series().groupby(index.to_period(period_code)).last().tolist()
    if len(grouped_period_ends) <= 1:
        return set()
    return {pd.Timestamp(date) for date in grouped_period_ends[:-1]}


def simulate_historical_rebalanced_values(
    history: pd.DataFrame, initial_values: pd.Series, rebalance_mode: str
) -> tuple[pd.Series, pd.Series, int]:
    ordered_history = history.copy()
    if ordered_history.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), 0

    target_weights = (initial_values / initial_values.sum()).reindex(ordered_history.columns).fillna(0.0)
    entry_prices = ordered_history.iloc[0]
    current_units = (initial_values.reindex(ordered_history.columns).fillna(0.0) / entry_prices).to_numpy(dtype=float)
    rebalance_dates = get_rebalance_dates(ordered_history.index, rebalance_mode)
    portfolio_values = []

    for date, prices in ordered_history.iterrows():
        price_vector = prices.to_numpy(dtype=float)
        current_values = current_units * price_vector
        portfolio_values.append(float(current_values.sum()))
        if pd.Timestamp(date) in rebalance_dates:
            total_value = float(current_values.sum())
            target_values = total_value * target_weights.to_numpy(dtype=float)
            current_units = np.divide(
                target_values,
                price_vector,
                out=np.zeros_like(target_values, dtype=float),
                where=price_vector != 0,
            )

    final_values = pd.Series(current_units * ordered_history.iloc[-1].to_numpy(dtype=float), index=ordered_history.columns)
    portfolio_history = pd.Series(portfolio_values, index=ordered_history.index)
    return portfolio_history, final_values, len(rebalance_dates)


def simulate_future_portfolio_paths(
    sampled_returns: np.ndarray,
    future_dates: pd.DatetimeIndex,
    initial_values: np.ndarray,
    rebalance_mode: str,
) -> tuple[np.ndarray, np.ndarray, int]:
    target_weights = initial_values / initial_values.sum()
    current_values = initial_values.astype(float).copy()
    portfolio_values = np.zeros(len(future_dates), dtype=float)
    rebalance_dates = get_rebalance_dates(future_dates, rebalance_mode)

    for day_index, date in enumerate(future_dates):
        current_values = current_values * (1 + sampled_returns[day_index])
        portfolio_values[day_index] = current_values.sum()
        if pd.Timestamp(date) in rebalance_dates:
            current_values = current_values.sum() * target_weights

    return portfolio_values, current_values, len(rebalance_dates)


def simulate_mock_backtest(
    watchlist: pd.DataFrame,
    price_history: pd.DataFrame,
    selected_assets: list,
    fake_amount: int,
    raw_weights: dict,
    interval_name: str | None = None,
    custom_start_date: pd.Timestamp | None = None,
    rebalance_mode: str = "Buy and hold",
) -> tuple[pd.DataFrame, dict]:
    df, allocation_meta = build_mock_allocation(
        watchlist, selected_assets, fake_amount, raw_weights
    )
    if df.empty:
        return df, allocation_meta

    simulation_history = ensure_price_history_for_tickers(
        price_history, df["ticker"].tolist(), period="5y"
    )
    tickers = [ticker for ticker in df["ticker"].tolist() if ticker in simulation_history.columns]
    if not tickers:
        return pd.DataFrame(), allocation_meta
    history = simulation_history[tickers].dropna(how="all").ffill()
    history = history.dropna(axis=1, how="all")
    if history.empty:
        return pd.DataFrame(), allocation_meta

    if custom_start_date is not None:
        custom_start_date = pd.Timestamp(custom_start_date).normalize()
        valid_dates = history.index[history.index >= custom_start_date]
        if len(valid_dates) < 2:
            return pd.DataFrame(), allocation_meta
        actual_start_date = pd.Timestamp(valid_dates[0])
        history = history.loc[actual_start_date:].ffill().dropna()
        reference_text = f"från {format_date_sv(actual_start_date)}"
        interval_label = format_date_sv(actual_start_date)
    else:
        interval = get_mock_backtest_intervals()[interval_name]
        start_index = max(0, len(history) - interval["trading_days"] - 1)
        history = history.iloc[start_index:].dropna(how="all")
        history = history.ffill().dropna()
        if history.empty:
            return pd.DataFrame(), allocation_meta
        actual_start_date = pd.Timestamp(history.index[0])
        reference_text = interval["reference_text"]
        interval_label = interval_name

    ticker_weights = df.set_index("ticker")["investment_amount"].reindex(history.columns).fillna(0.0)
    entry_prices = history.iloc[0]
    portfolio_history, final_values, rebalance_count = simulate_historical_rebalanced_values(
        history, ticker_weights, rebalance_mode
    )

    df = df.set_index("ticker").loc[history.columns].rename_axis("ticker").reset_index()
    df["entry_price"] = df["ticker"].map(entry_prices.to_dict())
    df["current_price"] = df["ticker"].map(history.iloc[-1].to_dict())
    df["units_bought"] = df["investment_amount"] / df["entry_price"]
    df["value_today"] = df["ticker"].map(final_values.to_dict())
    df["profit_loss"] = df["value_today"] - df["investment_amount"]
    df["return_pct"] = (df["value_today"] / df["investment_amount"] - 1) * 100

    invested = df["investment_amount"].sum()
    current_value = df["value_today"].sum()
    profit_loss = current_value - invested
    summary = {
        **allocation_meta,
        "interval_name": interval_label,
        "reference_text": reference_text,
        "actual_start_date": actual_start_date,
        "invested_amount": invested,
        "current_value": current_value,
        "profit_loss": profit_loss,
        "return_pct": (current_value / invested - 1) * 100 if invested else 0.0,
        "history_series": portfolio_history,
        "rebalance_mode": rebalance_mode,
        "rebalance_mode_label": get_mock_rebalance_modes()[rebalance_mode]["short_label"],
        "rebalance_count": rebalance_count,
    }
    return df.sort_values("return_pct", ascending=False), summary


def simulate_mock_future(
    watchlist: pd.DataFrame,
    price_history: pd.DataFrame,
    selected_assets: list,
    fake_amount: int,
    raw_weights: dict,
    horizon_name: str | None = None,
    custom_end_date: pd.Timestamp | None = None,
    simulations: int = 1000,
    block_size: int = 10,
    rebalance_mode: str = "Buy and hold",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    df, allocation_meta = build_mock_allocation(
        watchlist, selected_assets, fake_amount, raw_weights
    )
    if df.empty:
        return df, pd.DataFrame(), pd.DataFrame(), allocation_meta

    simulation_history = ensure_price_history_for_tickers(
        price_history, df["ticker"].tolist(), period="5y"
    )
    tickers = [ticker for ticker in df["ticker"].tolist() if ticker in simulation_history.columns]
    if not tickers:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta
    history = simulation_history[tickers].dropna(how="all").ffill().dropna()
    if history.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    returns = history.pct_change().dropna()
    if returns.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    last_history_date = pd.Timestamp(history.index[-1]).normalize()
    if custom_end_date is not None:
        custom_end_date = pd.Timestamp(custom_end_date).normalize()
        if custom_end_date <= last_history_date:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta
        future_dates = pd.bdate_range(last_history_date + pd.offsets.BDay(1), custom_end_date)
        label = f"fram till {format_date_sv(future_dates[-1])}" if len(future_dates) else "valt slutdatum"
        horizon_label = format_date_sv(custom_end_date)
    else:
        horizon = get_mock_future_horizons()[horizon_name]
        future_dates = pd.bdate_range(
            last_history_date + pd.offsets.BDay(1), periods=horizon["trading_days"]
        )
        label = horizon["label"]
        horizon_label = horizon_name

    horizon_days = len(future_dates)
    if horizon_days == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    df = df.set_index("ticker").loc[history.columns].rename_axis("ticker").reset_index()
    ordered_returns = returns[df["ticker"].tolist()].copy()
    if ordered_returns.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    returns_matrix = ordered_returns.to_numpy(dtype=float)
    block_size = min(max(5, block_size), len(returns_matrix))
    max_start_index = len(returns_matrix) - block_size + 1
    if max_start_index <= 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), allocation_meta

    rng = np.random.default_rng(42)
    initial_values = df["investment_amount"].to_numpy(dtype=float)
    portfolio_paths = np.zeros((horizon_days, simulations), dtype=float)
    asset_final_returns = np.zeros((len(initial_values), simulations), dtype=float)
    rebalance_counts = []

    for simulation_index in range(simulations):
        sampled_blocks = []
        sampled_days = 0
        while sampled_days < horizon_days:
            start_index = int(rng.integers(0, max_start_index))
            block = returns_matrix[start_index : start_index + block_size]
            sampled_blocks.append(block)
            sampled_days += len(block)

        sampled_returns = np.vstack(sampled_blocks)[:horizon_days]
        simulated_portfolio_values, final_asset_values, rebalance_count = simulate_future_portfolio_paths(
            sampled_returns,
            future_dates,
            initial_values,
            rebalance_mode,
        )
        portfolio_paths[:, simulation_index] = simulated_portfolio_values
        asset_final_returns[:, simulation_index] = (final_asset_values / initial_values) - 1
        rebalance_counts.append(rebalance_count)

    final_values = portfolio_paths[-1]
    path_df = pd.DataFrame(
        {
            "date": future_dates,
            "p10": np.percentile(portfolio_paths, 10, axis=1),
            "median": np.percentile(portfolio_paths, 50, axis=1),
            "p90": np.percentile(portfolio_paths, 90, axis=1),
        }
    )

    df["Nedre spann (P10)"] = np.percentile(asset_final_returns, 10, axis=1) * 100
    df["Median (P50)"] = np.percentile(asset_final_returns, 50, axis=1) * 100
    df["Övre spann (P90)"] = np.percentile(asset_final_returns, 90, axis=1) * 100

    summary_df = pd.DataFrame(
        [
            {
                "scenario": "Nedre spann (P10)",
                "future_value": np.percentile(final_values, 10),
                "return_pct": (np.percentile(final_values, 10) / fake_amount - 1) * 100 if fake_amount else 0.0,
            },
            {
                "scenario": "Median (P50)",
                "future_value": np.percentile(final_values, 50),
                "return_pct": (np.percentile(final_values, 50) / fake_amount - 1) * 100 if fake_amount else 0.0,
            },
            {
                "scenario": "Övre spann (P90)",
                "future_value": np.percentile(final_values, 90),
                "return_pct": (np.percentile(final_values, 90) / fake_amount - 1) * 100 if fake_amount else 0.0,
            },
        ]
    )
    summary = {
        **allocation_meta,
        "horizon_name": horizon_label,
        "label": label,
        "median_value": np.percentile(final_values, 50),
        "median_return_pct": (np.percentile(final_values, 50) / fake_amount - 1) * 100 if fake_amount else 0.0,
        "p10_value": np.percentile(final_values, 10),
        "p90_value": np.percentile(final_values, 90),
        "probability_positive_pct": float((final_values > fake_amount).mean() * 100),
        "probability_loss_10_pct": float((final_values < fake_amount * 0.9).mean() * 100),
        "simulations": simulations,
        "block_size": block_size,
        "rebalance_mode": rebalance_mode,
        "rebalance_mode_label": get_mock_rebalance_modes()[rebalance_mode]["short_label"],
        "rebalance_count": int(np.median(rebalance_counts)) if rebalance_counts else 0,
    }
    return df, summary_df, path_df, summary


def build_watch_notifications(
    watchlist: pd.DataFrame, price_history: pd.DataFrame, selected_assets: list, interval_name: str
) -> pd.DataFrame:
    interval = get_notification_intervals()[interval_name]
    watch_df = watchlist.loc[watchlist["company_name"].isin(selected_assets)].copy()

    if watch_df.empty:
        return watch_df

    watch_df["base_price"] = watch_df["ticker"].map(
        lambda ticker: get_interval_price(price_history[ticker], interval["trading_days"])
        if ticker in price_history.columns
        else np.nan
    )
    watch_df["current_price"] = watch_df["ticker"].map(
        lambda ticker: float(price_history[ticker].dropna().iloc[-1]) if ticker in price_history.columns and not price_history[ticker].dropna().empty else np.nan
    )
    watch_df = watch_df.dropna(subset=["base_price", "current_price"]).copy()
    if watch_df.empty:
        return watch_df

    watch_df["change_pct"] = ((watch_df["current_price"] / watch_df["base_price"]) - 1) * 100
    watch_df["direction"] = watch_df["change_pct"].apply(
        lambda x: "ökat" if x >= 0 else "minskat"
    )
    watch_df["next_send_at"] = pd.Timestamp.today().normalize() + interval["offset"]
    watch_df["notification_text"] = watch_df.apply(
        lambda row: (
            f"{row['company_name']} har {row['direction']} med "
            f"{format_pct(abs(row['change_pct']))} sedan {interval['reference_text']}."
        ),
        axis=1,
    )
    return watch_df.sort_values("change_pct", ascending=False)


def build_rebalance_notification(
    df: pd.DataFrame, trade_plan: pd.DataFrame, profile_name: str, interval_name: str
) -> dict:
    interval = get_notification_intervals()[interval_name]
    today = pd.Timestamp.today().normalize()
    next_send_at = today + interval["offset"]

    largest_over = df.sort_values("weight_gap_pct").iloc[0]
    largest_under = df.sort_values("weight_gap_pct", ascending=False).iloc[0]
    biggest_change = df.iloc[df["trailing_1m_pct"].abs().argmax()]

    sell_row = trade_plan.loc[trade_plan["trade_action"] == "Sälj"].head(1)
    buy_rows = trade_plan.loc[trade_plan["trade_action"] == "Köp"].head(2)

    actions = []
    if not sell_row.empty:
        actions.append(
            f"sälj {sell_row.iloc[0]['name']} för {format_sek(sell_row.iloc[0]['trade_amount'])}"
        )
    for _, row in buy_rows.iterrows():
        actions.append(f"öka {row['name']} med {format_sek(row['trade_amount'])}")

    action_text = ", ".join(actions[:3]) if actions else "gör mindre justeringar"
    short_text = (
        f"Dags för rebalansering. {largest_over['category']} ligger över mål och "
        f"{largest_under['category']} ligger under."
    )
    body = (
        f"Nu är det dags för {interval_name.lower()} översyn. "
        f"Under den senaste månaden har {biggest_change['name']} rört sig "
        f"{format_signed_pct(biggest_change['trailing_1m_pct'])}. "
        f"Just nu ligger {largest_over['category']} {format_pct(abs(largest_over['weight_gap_pct']))} "
        f"över mål, medan {largest_under['category']} ligger "
        f"{format_pct(abs(largest_under['weight_gap_pct']))} under mål. "
        f"Om du vill ligga i linje med profilen {profile_name} kan du se över om det är läge att {action_text}."
    )
    return {
        "title": "Dags för rebalansering",
        "body": body,
        "short_text": short_text,
        "next_send_at": next_send_at,
    }


def simulate_contribution(df: pd.DataFrame, extra_contribution: int) -> pd.DataFrame:
    scenario = df.copy()
    total_after = scenario["value_sek"].sum() + extra_contribution
    scenario["target_after_cash"] = total_after * scenario["target_weight"]
    scenario["cash_gap"] = (scenario["target_after_cash"] - scenario["value_sek"]).clip(lower=0)

    # Nytt kapital går först till det som ligger under målvikten, så att säljbehovet minskar.
    if extra_contribution <= 0:
        scenario["cash_allocation"] = 0.0
    elif scenario["cash_gap"].sum() >= extra_contribution:
        scenario["cash_allocation"] = (
            extra_contribution * scenario["cash_gap"] / scenario["cash_gap"].sum()
        )
    else:
        remaining = extra_contribution - scenario["cash_gap"].sum()
        scenario["cash_allocation"] = scenario["cash_gap"] + (remaining * scenario["target_weight"])

    scenario["value_after_cash"] = scenario["value_sek"] + scenario["cash_allocation"]
    scenario["weight_after_cash_pct"] = scenario["value_after_cash"] / total_after * 100
    scenario["remaining_gap_pct"] = (
        scenario["target_weight_pct"] - scenario["weight_after_cash_pct"]
    )
    return scenario


def render_css() -> None:
    css = """
    <style>
    html, body, [class*="css"] {
        font-family: savr-sans-vf, savr-sans, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .stApp {
        background: __BG__;
        color: __INK__;
        accent-color: __INK__;
    }
    [data-testid="stAppViewContainer"] > .main {
        background: __BG__;
    }
    [data-testid="stSidebar"] {
        background: #FFFFFF;
        border-right: 1px solid __BORDER__;
    }
    [data-testid="stSidebar"] * {
        color: __INK__;
    }
    .block-container {
        max-width: 1180px;
        padding-top: 1.1rem;
        padding-bottom: 3rem;
    }
    .savr-topbar {
        background: __SURFACE__;
        border: 1px solid __BORDER__;
        border-radius: 30px;
        padding: 1rem 1.15rem;
        display: flex;
        gap: 0.85rem;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.15rem;
        box-shadow: 0 10px 28px rgba(20, 35, 59, 0.05);
    }
    .savr-topbar-left {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
    }
    .brand-wordmark {
        font-weight: 800;
        font-size: 1.7rem;
        letter-spacing: -0.04em;
        color: __INK__;
        margin-right: 0.4rem;
    }
    .market-chip, .header-pill, .search-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        border-radius: 999px;
        border: 1px solid __BORDER__;
        background: #F8F8FA;
        color: __INK__;
        padding: 0.65rem 0.9rem;
        font-size: 0.92rem;
        white-space: nowrap;
    }
    .market-chip strong {
        color: __ACCENT_BLUE__;
        font-weight: 700;
    }
    .search-pill {
        min-width: 280px;
        color: __INK_SOFT__;
        justify-content: flex-start;
    }
    .header-pill-solid {
        background: __INK__;
        color: white;
        border-color: __INK__;
        font-weight: 600;
    }
    .page-header {
        padding: 0.4rem 0 0.9rem 0;
        margin-bottom: 0.75rem;
    }
    .page-chip-row {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
        margin-bottom: 0.9rem;
    }
    .page-chip {
        display: inline-flex;
        align-items: center;
        border: 1px solid __BORDER__;
        border-radius: 999px;
        padding: 0.55rem 0.9rem;
        background: #FFFFFF;
        color: __INK__;
        font-size: 0.92rem;
        font-weight: 600;
    }
    .page-chip.active {
        background: #ECEDEF;
        border-color: #D3D7DD;
    }
    .page-header h1 {
        margin: 0;
        font-size: 2.05rem;
        letter-spacing: -0.04em;
        color: __INK__;
    }
    .page-header p {
        margin: 0.45rem 0 0 0;
        font-size: 1rem;
        color: __INK_SOFT__;
        max-width: 840px;
        line-height: 1.5;
    }
    .page-context {
        margin-top: 0.75rem;
        padding: 0.9rem 1rem;
        border-radius: 20px;
        border: 1px solid __BORDER__;
        background: #F8F8FA;
        min-height: 88px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .page-context strong {
        color: __INK__;
        font-size: 0.95rem;
        margin-bottom: 0.2rem;
    }
    .page-context p {
        margin: 0;
        max-width: none;
        color: __INK_SOFT__;
        font-size: 0.96rem;
        line-height: 1.55;
    }
    .panel {
        background: __SURFACE__;
        border: 1px solid __BORDER__;
        border-radius: 24px;
        padding: 1.1rem 1.2rem;
        box-shadow: 0 12px 30px rgba(20, 35, 59, 0.045);
    }
    div[data-testid="stMetric"] {
        background: __SURFACE__;
        border: 1px solid __BORDER__;
        padding: 1rem 1.1rem;
        border-radius: 24px;
        box-shadow: 0 12px 30px rgba(20, 35, 59, 0.045);
    }
    div[data-testid="stMetricLabel"] p {
        color: __INK_SOFT__;
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        color: __INK__;
        letter-spacing: -0.04em;
    }
    .insight {
        padding: 1rem 1.1rem;
        border-radius: 20px;
        margin-bottom: 0.8rem;
        border: 1px solid transparent;
    }
    .insight h4 {
        margin: 0 0 0.35rem 0;
        font-size: 1rem;
    }
    .insight p {
        margin: 0;
        color: __INK_SOFT__;
        line-height: 1.5;
    }
    .warning {
        background: #F8F8FA;
        border-color: __BORDER__;
    }
    .info {
        background: __ACCENT_BLUE_SOFT__;
        border-color: #D8DDFF;
    }
    .success {
        background: __ACCENT_BLUE_SOFT__;
        border-color: #D8DDFF;
    }
    .small-note {
        color: __INK_SOFT__;
        font-size: 0.95rem;
    }
    .section-card {
        background: __SURFACE__;
        border: 1px solid __BORDER__;
        border-radius: 28px;
        padding: 1.35rem 1.4rem;
        box-shadow: 0 12px 30px rgba(20, 35, 59, 0.045);
    }
    .micro-kpi {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
        gap: 0.75rem;
        margin-top: 0.9rem;
    }
    .micro-kpi div {
        border-radius: 18px;
        border: 1px solid __BORDER__;
        padding: 0.85rem 0.9rem;
        background: #F8F8FA;
        min-width: 0;
        line-height: 1.45;
        word-break: normal;
        overflow-wrap: break-word;
        hyphens: auto;
    }
    .micro-kpi strong {
        display: block;
        font-size: 1.1rem;
        color: __INK__;
        margin-top: 0.2rem;
        line-height: 1.35;
        word-break: normal;
        overflow-wrap: break-word;
        hyphens: auto;
    }
    .mock-note {
        color: __INK_SOFT__;
        font-size: 0.92rem;
        margin-top: 0.7rem;
    }
    .sidebar-brand {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        color: __INK__;
        margin: 0.3rem 0 1.1rem 0.1rem;
    }
    .sidebar-nav-section {
        color: __INK_SOFT__;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 1.1rem 0 0.45rem 0.1rem;
    }
    .sidebar-nav-item {
        padding: 0.82rem 0.95rem;
        border-radius: 16px;
        color: __INK__;
        margin-bottom: 0.18rem;
    }
    .sidebar-nav-item.active {
        background: #F8F8FA;
        border: 1px solid __BORDER__;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.6rem;
    }
    .stTabs [data-baseweb="tab"] {
        background: #FFFFFF;
        border: 1px solid __BORDER__;
        border-radius: 999px;
        padding: 0.5rem 1rem;
        color: __INK__;
    }
    .stTabs [aria-selected="true"] {
        background: #ECEDEF !important;
        border-color: #D3D7DD !important;
        color: __INK__ !important;
        font-weight: 700 !important;
    }
    .stButton > button {
        border-radius: 999px;
        border: 1px solid __BORDER__;
        background: __SURFACE__;
        color: __INK__;
        font-weight: 600;
    }
    .stButton > button:hover {
        border-color: __INK__;
        color: __INK__;
    }
    .stTextInput input, .stNumberInput input {
        border-radius: 16px;
    }
    div[role="radiogroup"] label {
        border: 1px solid __BORDER__;
        border-radius: 16px;
        padding: 0.78rem 1rem;
        background: #FFFFFF;
    }
    div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background: #ECEDEF !important;
        border-color: #D3D7DD !important;
    }
    .stSlider [data-baseweb="slider"] [role="slider"] {
        background-color: __INK__ !important;
        border-color: __INK__ !important;
        box-shadow: none !important;
    }
    .stSlider [data-baseweb="slider"] [role="slider"] * {
        color: __INK__ !important;
        fill: __INK__ !important;
        stroke: __INK__ !important;
    }
    .stSlider [data-baseweb="slider"] > div {
        background: transparent !important;
    }
    .stSlider [data-baseweb="slider"] p,
    .stSlider [data-baseweb="slider"] label,
    .stSlider [data-baseweb="slider"] span {
        color: __INK__ !important;
        background: transparent !important;
    }
    [data-baseweb="tag"] {
        background: #F3F4F6 !important;
        border: 1px solid __BORDER__ !important;
        color: __INK__ !important;
    }
    [data-baseweb="tag"] * {
        color: __INK__ !important;
        fill: __INK__ !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        padding: 0.82rem 0.95rem;
        margin-bottom: 0.2rem;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: #ECEDEF !important;
        border-color: #D3D7DD !important;
    }
    .stDataFrame, .stPlotlyChart {
        background: transparent;
    }
    </style>
    """

    css = (
        css.replace("__BG__", SAVR_THEME["bg"])
        .replace("__INK__", SAVR_THEME["ink"])
        .replace("__INK_SOFT__", SAVR_THEME["ink_soft"])
        .replace("__SURFACE__", SAVR_THEME["surface"])
        .replace("__BORDER__", SAVR_THEME["border"])
        .replace("__BRAND_RED_DARK__", SAVR_THEME["brand_red_dark"])
        .replace("__BRAND_RED__", SAVR_THEME["brand_red"])
        .replace("__ACCENT_BLUE__", SAVR_THEME["accent_blue"])
        .replace("__ACCENT_BLUE_SOFT__", SAVR_THEME["accent_blue_soft"])
    )
    st.markdown(css, unsafe_allow_html=True)


def render_insights(insights: list) -> None:
    for insight in insights:
        st.markdown(
            f"""
            <div class="insight {insight['tone']}">
                <h4>{insight['title']}</h4>
                <p>{insight['body']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_notification_cards(title: str, messages: list, tone: str = "info") -> None:
    st.markdown(f"#### {title}")
    if not messages:
        st.markdown(
            """
            <div class="insight info">
                <h4>Inga notiser valda ännu</h4>
                <p>Välj innehav eller intervall för att skapa en första notisfeed.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for message in messages:
        st.markdown(
            f"""
            <div class="insight {tone}">
                <h4>{message['title']}</h4>
                <p>{message['body']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def build_current_allocation_chart(df: pd.DataFrame) -> go.Figure:
    fig = px.pie(
        df,
        values="value_sek",
        names="category",
        hole=0.62,
        color_discrete_sequence=BRAND_COLORS,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=10),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_comparison_chart(df: pd.DataFrame) -> go.Figure:
    comparison = df[["name", "current_weight_pct", "target_weight_pct"]].melt(
        id_vars="name",
        value_vars=["current_weight_pct", "target_weight_pct"],
        var_name="scenario",
        value_name="weight_pct",
    )
    comparison["scenario"] = comparison["scenario"].map(
        {
            "current_weight_pct": "Nuvarande",
            "target_weight_pct": "Föreslagen",
        }
    )
    fig = px.bar(
        comparison,
        x="name",
        y="weight_pct",
        color="scenario",
        barmode="group",
        color_discrete_map={
            "Nuvarande": "#C7D0DD",
            "Föreslagen": SAVR_THEME["accent_blue"],
        },
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Vikt (%)",
        legend_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_contribution_chart(df: pd.DataFrame) -> go.Figure:
    comparison = df[["name", "weight_after_cash_pct", "target_weight_pct"]].melt(
        id_vars="name",
        value_vars=["weight_after_cash_pct", "target_weight_pct"],
        var_name="scenario",
        value_name="weight_pct",
    )
    comparison["scenario"] = comparison["scenario"].map(
        {
            "weight_after_cash_pct": "Efter insättning",
            "target_weight_pct": "Målvikt",
        }
    )
    fig = px.bar(
        comparison,
        x="name",
        y="weight_pct",
        color="scenario",
        barmode="group",
        color_discrete_map={
            "Efter insättning": "#8A92FF",
            "Målvikt": SAVR_THEME["accent_blue"],
        },
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Vikt (%)",
        legend_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_mock_backtest_chart(history_series: pd.Series, invested_amount: float) -> go.Figure:
    chart_df = pd.DataFrame({"date": history_series.index, "value": history_series.values})
    fig = px.area(chart_df, x="date", y="value")
    fig.update_traces(
        line=dict(color=SAVR_THEME["accent_blue"], width=3),
        fillcolor="rgba(91, 95, 239, 0.12)",
    )
    fig.add_hline(
        y=invested_amount,
        line_dash="dot",
        line_color=SAVR_THEME["ink_soft"],
        annotation_text="Startbelopp",
        annotation_position="top left",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Värde (kr)",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_mock_future_chart(path_df: pd.DataFrame, start_value: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=path_df["date"],
            y=path_df["p90"],
            mode="lines",
            line=dict(color="rgba(102,124,255,0)"),
            hoverinfo="skip",
            showlegend=False,
            name="Övre spann (P90)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=path_df["date"],
            y=path_df["p10"],
            mode="lines",
            line=dict(color="rgba(102,124,255,0)"),
            fill="tonexty",
            fillcolor="rgba(102,124,255,0.18)",
            name="Sannolikhetsband (P10-P90)",
            hovertemplate="%{y:,.0f} kr<extra>Nedre spann</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=path_df["date"],
            y=path_df["median"],
            mode="lines",
            line=dict(color=SAVR_THEME["accent_blue"], width=3),
            name="Median (P50)",
            hovertemplate="%{y:,.0f} kr<extra>Median</extra>",
        )
    )
    fig.add_hline(
        y=start_value,
        line_dash="dot",
        line_color=SAVR_THEME["ink_soft"],
        annotation_text="Investerat belopp",
        annotation_position="top left",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="",
        yaxis_title="Möjligt värde (kr)",
        legend_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def set_session_defaults(defaults: dict) -> None:
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def normalize_legacy_state() -> None:
    module_aliases = {
        "Lär med fake-pengar": "TestSAVR",
        "Testinvest": "TestSAVR",
    }
    active_module = st.session_state.get("active_module")
    if active_module in module_aliases:
        st.session_state.active_module = module_aliases[active_module]

    if st.session_state.get("selected_profile") == "Forsiktig":
        st.session_state.selected_profile = "Försiktig"
    if st.session_state.get("profile_name") == "Forsiktig profil":
        st.session_state.profile_name = "Försiktig profil"
    if st.session_state.get("mock_rebalance_mode") == "Köp och behåll":
        st.session_state.mock_rebalance_mode = "Buy and hold"
    if st.session_state.get("mock_source") not in {None, "Egna instrument", "Portfölj från Portföljkollen"}:
        st.session_state.mock_source = "Egna instrument"
    if st.session_state.get("rebalancer_header_chip") in {"Rebalansering", "Smart Rebalancer"}:
        st.session_state.rebalancer_header_chip = "Portföljkollen"
    if st.session_state.get("testinvest_header_chip") == "Testinvest":
        st.session_state.testinvest_header_chip = "TestSAVR"


def initialize_session_state(
    default_profile: dict,
    category_order: list[str],
    default_backtest_date: pd.Timestamp,
    default_future_date: pd.Timestamp,
) -> None:
    default_instruments = get_default_category_instrument_map()
    set_session_defaults(
        {
            "profile_name": "Min profil",
            "risk_appetite": int(default_profile["risk_appetite"]),
            "analysis_window": "3 år",
            "risk_free_rate_pct": 2.0,
            "concentration_threshold": default_profile["max_single_holding"],
            "equity_buffer": int(default_profile["equity_buffer"]),
            "category_gap_threshold": int(default_profile["category_gap_threshold"]),
            "top_three_threshold": int(default_profile["top_three_threshold"]),
            "minimum_trade_size": int(default_profile["minimum_trade_size"]),
            "min_portfolio_sharpe": float(default_profile["min_portfolio_sharpe"]),
            "max_portfolio_volatility": float(default_profile["max_portfolio_volatility"]),
            "max_drawdown_tolerance": float(default_profile["max_drawdown_tolerance"]),
            "active_module": "Rebalansering",
            "selected_profile": "Balanserad",
            "watch_selection": ["Apple", "Investor B"],
            "watch_interval": "Månadsvis",
            "rebalance_interval": "Månadsvis",
            "watch_active": False,
            "rebalance_active": False,
            "mock_source": "Egna instrument",
            "mock_assets": ["Apple", "Microsoft", "Investor B"],
            "mock_amount": 10000,
            "mock_backtest_interval": "1 månad bakåt",
            "mock_future_horizon": "1 månad framåt",
            "mock_weight_mode": "Likavikt",
            "mock_rebalance_mode": "Buy and hold",
            "mock_backtest_mode": "Snabbval",
            "mock_future_mode": "Snabbval",
            "mock_backtest_custom_date": default_backtest_date.date(),
            "mock_future_custom_date": default_future_date.date(),
            "mock_backtest_custom_text": "",
            "mock_future_custom_text": "",
            "rebalancer_header_chip": "Portföljkollen",
            "testinvest_header_chip": "TestSAVR",
        }
    )

    for question in get_risk_questionnaire():
        if question["key"] not in st.session_state:
            midpoint_index = min(1, len(question["options"]) - 1)
            st.session_state[question["key"]] = question["options"][midpoint_index]["label"]

    for category in category_order:
        weight_key = f"target_weight_{category}"
        if weight_key not in st.session_state:
            st.session_state[weight_key] = float(default_profile["target_weights"][category])
        instrument_key = f"category_instrument_{category}"
        if instrument_key not in st.session_state:
            st.session_state[instrument_key] = default_instruments[category]

    normalize_legacy_state()


def render_sidebar_navigation() -> str:
    with st.sidebar:
        st.markdown('<div class="sidebar-brand">SAVR</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="sidebar-nav-section">Meny</div>
            <div class="sidebar-nav-item">Hem</div>
            <div class="sidebar-nav-item">Innehav</div>
            <div class="sidebar-nav-item">Bevaka</div>
            <div class="sidebar-nav-item">Upptäck</div>
            <div class="sidebar-nav-section">Nya verktyg</div>
            """,
            unsafe_allow_html=True,
        )
        active_module = st.radio(
            "Välj verktyg",
            options=["Rebalansering", "TestSAVR"],
            key="active_module",
            label_visibility="collapsed",
            format_func=lambda option: (
                "SAVR Portföljkollen" if option == "Rebalansering" else "TestSAVR"
            ),
        )
        st.caption("Välj ett verktyg för att analysera portföljen eller testa ett scenario.")
    return active_module


def get_module_header_config(active_module: str) -> tuple[str, str, list[str], dict[str, tuple[str, str]]]:
    if active_module == "Rebalansering":
        return (
            "SAVR Portföljkollen",
            "rebalancer_header_chip",
            ["Portföljkollen", "Marknadsdata", "Riskprofil"],
            {
                "Portföljkollen": (
                    "Vad verktyget gör",
                    "Du får hjälp att förstå portföljen, upptäcka obalanser och se tydliga köp- och säljförslag utifrån din målprofil.",
                ),
                "Marknadsdata": (
                    "Datakälla",
                    "Analysen bygger på aktuella priser, valutakurser och historisk utveckling för portföljens innehav.",
                ),
                "Riskprofil": (
                    "Hur riskprofilen används",
                    "Riskprofilen sätter ramar för aktieandel, koncentration och hur stora svängningar portföljen bör tåla. Standardprofilerna ger färdiga riktlinjer, medan Egen profil låter dig styra själv.",
                ),
            },
        )

    return (
        "TestSAVR",
        "testinvest_header_chip",
        ["TestSAVR", "Bootstrap-Monte Carlo", "Marknadsdata"],
        {
            "TestSAVR": (
                "Vad verktyget gör",
                "Du kan prova idéer med ett testbelopp, se hur olika val hade påverkat utvecklingen och jämföra möjliga framtidsutfall innan riktiga beslut tas.",
            ),
            "Bootstrap-Monte Carlo": (
                "Så fungerar Bootstrap-Monte Carlo",
                "Framtidssimuleringen återanvänder verkliga historiska returblock från de valda instrumenten i stället för ett enda fast basscenario. Det ger ett spann av möjliga framtida vägar och sammanfattas i P10, P50 och P90.",
            ),
            "Marknadsdata": (
                "Datakälla",
                "TestSAVR bygger på historiska prisrörelser för de instrument du väljer.",
            ),
        },
    )


def render_topbar_and_header(
    page_title: str,
    header_context_key: str,
    page_tags: list[str],
    header_context_map: dict[str, tuple[str, str]],
    market_chip_history: pd.DataFrame,
) -> None:
    if st.session_state.get(header_context_key) not in page_tags:
        st.session_state[header_context_key] = page_tags[0]

    st.markdown(
        f"""
        <div class="savr-topbar">
            <div class="savr-topbar-left">
                <div class="brand-wordmark">SAVR</div>
                <div class="market-chip">{build_market_chip_label(market_chip_history, '^OMX', 'OMXS30')}</div>
                <div class="market-chip">{build_market_chip_label(market_chip_history, '^IXIC', 'NASDAQ')}</div>
                <div class="search-pill">Sök efter värdepapper</div>
            </div>
            <div class="savr-topbar-left">
                <div class="header-pill">Ordrar 0</div>
                <div class="header-pill header-pill-solid">Sätt in pengar</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    header_context = st.radio(
        "Sidinfo",
        options=page_tags,
        key=header_context_key,
        horizontal=True,
        label_visibility="collapsed",
    )
    context_title, context_copy = header_context_map[header_context]
    st.markdown(
        f"""
        <div class="page-header">
            <h1>{page_title}</h1>
            <div class="page-context">
                <strong>{context_title}</strong>
                <p>{context_copy}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_market_context(
    portfolio_template: pd.DataFrame,
    watchlist_template: pd.DataFrame,
    analysis_window: str,
    risk_free_rate_pct: float,
) -> dict:
    category_instrument_lookup = get_category_instrument_lookup()
    fx_tickers = get_fx_tickers(
        portfolio_template["currency"].tolist()
        + watchlist_template["currency"].tolist()
        + [instrument["currency"] for instrument in category_instrument_lookup.values()]
    )
    all_tickers = tuple(
        sorted(
            set(
                portfolio_template["ticker"].tolist()
                + watchlist_template["ticker"].tolist()
                + list(category_instrument_lookup.keys())
                + list(fx_tickers)
            )
        )
    )
    full_price_history = fetch_price_history(all_tickers, period="5y")
    portfolio = build_live_portfolio_values(portfolio_template, full_price_history)
    watchlist = build_live_watchlist_values(watchlist_template, full_price_history)
    instrument_universe = build_yfinance_instrument_universe(portfolio, watchlist)

    try:
        savr_fund_catalog = fetch_savr_public_fund_catalog()
    except Exception:
        savr_fund_catalog = pd.DataFrame(columns=["id", "isin", "currency"])

    market_chip_history = fetch_price_history(("^OMX", "^IXIC"), period="1mo")
    analysis_history = slice_price_history(
        full_price_history, get_analysis_windows()[analysis_window]["trading_days"]
    )
    portfolio_asset_metrics, portfolio_market_summary = compute_historical_metrics(
        analysis_history,
        weights=portfolio.set_index("ticker")["value_sek"].to_dict(),
        risk_free_rate_pct=risk_free_rate_pct,
    )
    return {
        "full_price_history": full_price_history,
        "analysis_history": analysis_history,
        "portfolio": portfolio,
        "watchlist": watchlist,
        "instrument_universe": instrument_universe,
        "savr_fund_catalog": savr_fund_catalog,
        "market_chip_history": market_chip_history,
        "portfolio_asset_metrics": portfolio_asset_metrics,
        "portfolio_market_summary": portfolio_market_summary,
    }


def build_selected_profile_config(
    profiles: dict,
    selected_profile: str,
    selected_profile_name: str,
    raw_target_weights: dict,
) -> dict:
    if selected_profile in profiles:
        return {
            **profiles[selected_profile],
            "target_weights": dict(profiles[selected_profile]["target_weights"]),
            "raw_weight_total": 100.0,
            "profile_name": selected_profile_name,
        }

    return build_personal_profile(
        selected_profile_name,
        raw_target_weights,
        int(st.session_state.concentration_threshold),
    )


def build_personalization_settings(portfolio_market_summary: dict) -> dict:
    return {
        "concentration_threshold": int(st.session_state.concentration_threshold),
        "equity_buffer": int(st.session_state.equity_buffer),
        "category_gap_threshold": int(st.session_state.category_gap_threshold),
        "top_three_threshold": int(st.session_state.top_three_threshold),
        "min_portfolio_sharpe": float(st.session_state.min_portfolio_sharpe),
        "max_portfolio_volatility": float(st.session_state.max_portfolio_volatility),
        "max_drawdown_tolerance": float(st.session_state.max_drawdown_tolerance),
        "market_summary": portfolio_market_summary,
    }


def get_history_date_bounds(full_price_history: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    if full_price_history.empty:
        return (
            pd.Timestamp.today().normalize() - pd.DateOffset(years=1),
            pd.Timestamp.today().normalize(),
        )

    return (
        pd.Timestamp(full_price_history.index.min()).normalize(),
        pd.Timestamp(full_price_history.index.max()).normalize(),
    )


def render_data_source_cards(
    portfolio: pd.DataFrame,
    watchlist: pd.DataFrame,
    instrument_universe: pd.DataFrame,
    savr_fund_catalog: pd.DataFrame,
) -> None:
    st.write("")
    source_col_1, source_col_2, source_col_3 = st.columns(3, gap="large")
    source_col_1.markdown(
        f"""
        <div class="section-card">
            <strong>Portföljöversikt</strong>
            <div class="mock-note">Portföljen följs upp med aktuella värden och historisk utveckling för de innehav som ingår i analysen.</div>
            <div class="micro-kpi">
                <div>
                    Innehav
                    <strong>{len(portfolio)}</strong>
                </div>
                <div>
                    Valuta
                    <strong>USD/SEK</strong>
                </div>
                <div>
                    Källa
                    <strong>Marknadsdata</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    source_col_2.markdown(
        f"""
        <div class="section-card">
            <strong>TestSAVR</strong>
            <div class="mock-note">Samma urval av instrument kan användas för bevakning, bakåtblick och framtidsscenarier.</div>
            <div class="micro-kpi">
                <div>
                    Instrument
                    <strong>{len(instrument_universe)}</strong>
                </div>
                <div>
                    Aktier / ETF:er
                    <strong>{len(watchlist)} / {len(portfolio)}</strong>
                </div>
                <div>
                    Källa
                    <strong>Marknadsdata</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    source_col_3.markdown(
        f"""
        <div class="section-card">
            <strong>Fondinformation</strong>
            <div class="mock-note">Fondöversikten kompletteras med information från SAVR:s fondutbud.</div>
            <div class="micro-kpi">
                <div>
                    Fonder
                    <strong>{len(savr_fund_catalog)}</strong>
                </div>
                <div>
                    ISIN
                    <strong>{savr_fund_catalog['isin'].nunique() if not savr_fund_catalog.empty else 0}</strong>
                </div>
                <div>
                    Källa
                    <strong>SAVR</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mode_summary_panel(
    active_module: str,
    profiles: dict,
    selected_profile: str,
    selected_profile_name: str,
    selected_profile_config: dict,
) -> None:
    if active_module == "Rebalansering":
        profile_label = selected_profile if selected_profile in profiles else selected_profile_name
        st.markdown(
            f"""
            <div class="panel">
                <strong>Profil:</strong> {profile_label}<br>
                <strong>Riskbenägenhet:</strong> {st.session_state.risk_appetite} / 10<br>
                <strong>Historiskt fönster:</strong> {st.session_state.analysis_window}<br>
                <strong>Mål för aktieandel:</strong> {format_pct(selected_profile_config['equity_target'])}<br>
                <span class="small-note">{selected_profile_config['description']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        """
        <div class="panel">
            <strong>Läge:</strong> TestSAVR<br>
            <strong>Syfte:</strong> Testa idéer, se historisk utveckling och förstå risk utan verkligt kapital.<br>
            <span class="small-note">Det här läget fokuserar på pedagogik och simulering med riktig historik samt scenario-baserad framåtblick.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    render_css()

    profiles = get_risk_profiles()
    notification_intervals = get_notification_intervals()
    category_order = list(profiles["Balanserad"]["target_weights"].keys())
    default_profile = profiles["Balanserad"]
    analysis_windows = get_analysis_windows()
    default_category_instruments = get_default_category_instrument_map()
    set_session_defaults(
        {
            "profile_name": "Min profil",
            "risk_appetite": int(default_profile["risk_appetite"]),
            "analysis_window": "3 år",
            "risk_free_rate_pct": 2.0,
            "concentration_threshold": default_profile["max_single_holding"],
            "equity_buffer": int(default_profile["equity_buffer"]),
            "category_gap_threshold": int(default_profile["category_gap_threshold"]),
            "top_three_threshold": int(default_profile["top_three_threshold"]),
            "minimum_trade_size": int(default_profile["minimum_trade_size"]),
            "min_portfolio_sharpe": float(default_profile["min_portfolio_sharpe"]),
            "max_portfolio_volatility": float(default_profile["max_portfolio_volatility"]),
            "max_drawdown_tolerance": float(default_profile["max_drawdown_tolerance"]),
            "active_module": "Rebalansering",
            "selected_profile": "Balanserad",
            **{
                f"category_instrument_{category}": ticker
                for category, ticker in default_category_instruments.items()
            },
        }
    )
    normalize_legacy_state()

    active_category_instruments = get_active_category_instrument_map(
        st.session_state.selected_profile,
        category_order,
    )
    portfolio_template = load_live_portfolio_template(active_category_instruments)
    watchlist_template = load_live_watchlist_template()

    market_context = load_market_context(
        portfolio_template,
        watchlist_template,
        st.session_state.analysis_window,
        float(st.session_state.risk_free_rate_pct),
    )
    full_price_history = market_context["full_price_history"]
    analysis_history = market_context["analysis_history"]
    portfolio = market_context["portfolio"]
    watchlist = market_context["watchlist"]
    instrument_universe = market_context["instrument_universe"]
    savr_fund_catalog = market_context["savr_fund_catalog"]
    market_chip_history = market_context["market_chip_history"]
    portfolio_asset_metrics = market_context["portfolio_asset_metrics"]
    portfolio_market_summary = market_context["portfolio_market_summary"]

    history_first_date, history_last_date = get_history_date_bounds(full_price_history)
    default_backtest_date = max(history_first_date, history_last_date - pd.DateOffset(months=1))
    default_future_date = history_last_date + pd.DateOffset(months=6)
    initialize_session_state(
        default_profile,
        category_order,
        default_backtest_date,
        default_future_date,
    )
    active_module = render_sidebar_navigation()

    selected_profile = st.session_state.selected_profile
    raw_target_weights = {
        category: float(st.session_state[f"target_weight_{category}"])
        for category in category_order
    }
    selected_profile_name = st.session_state.profile_name.strip() or selected_profile
    selected_profile_config = build_selected_profile_config(
        profiles,
        selected_profile,
        selected_profile_name,
        raw_target_weights,
    )
    personalization_settings = build_personalization_settings(portfolio_market_summary)
    portfolio_df = prepare_portfolio(portfolio, selected_profile_config, portfolio_asset_metrics)
    metrics = calculate_metrics(portfolio_df, selected_profile_config, portfolio_market_summary)
    insights = detect_imbalances(
        portfolio_df,
        selected_profile_name,
        selected_profile_config,
        personalization_settings,
    )
    trade_plan = build_trade_plan(portfolio_df, int(st.session_state.minimum_trade_size))
    page_title, header_context_key, page_tags, header_context_map = get_module_header_config(
        active_module
    )
    render_topbar_and_header(
        page_title,
        header_context_key,
        page_tags,
        header_context_map,
        market_chip_history,
    )

    render_mode_summary_panel(
        active_module,
        profiles,
        selected_profile,
        selected_profile_name,
        selected_profile_config,
    )

    if active_module == "Rebalansering":
        st.write("")
        st.subheader("Profilinställningar för rebalansering")
        st.caption(
            "Här anpassar du målprofil, riskramar och målvikter för rebalanseringen."
        )

        settings_profile_tab, settings_questionnaire_tab, settings_risk_tab, settings_weight_tab = st.tabs(
            ["Profil", "Riskprofil-enkät", "Riskramar", "Målvikter"]
        )
        custom_profile_enabled = st.session_state.selected_profile == "Egen profil"

        with settings_profile_tab:
            profile_col, profile_help_col = st.columns([1.15, 0.85], gap="large")

            with profile_col:
                st.selectbox(
                    "Välj basprofil",
                    options=[*profiles.keys(), "Egen profil"],
                    key="selected_profile",
                    on_change=handle_profile_selection_change,
                )
                st.text_input("Namn på kundprofil", key="profile_name")
                st.slider(
                    "Riskbenägenhet",
                    min_value=1,
                    max_value=10,
                    step=1,
                    key="risk_appetite",
                    disabled=not custom_profile_enabled,
                )
                st.caption(
                    "Standardprofilerna låser risknivå och mål. Välj Egen profil för att själv justera riskbenägenhet, riskramar och målvikter."
                )
                st.selectbox(
                    "Historiskt analysfönster",
                    options=list(analysis_windows.keys()),
                    key="analysis_window",
                )
                st.slider(
                    "Riskfri ränta (%)",
                    min_value=0.0,
                    max_value=6.0,
                    step=0.1,
                    key="risk_free_rate_pct",
                )

            with profile_help_col:
                st.markdown(
                    f"""
                    <div class="section-card">
                        <strong>Profilstatus</strong>
                        <div class="micro-kpi">
                            <div>
                                Basprofil
                                <strong>{st.session_state.selected_profile}</strong>
                            </div>
                            <div>
                                Risknivå
                                <strong>{st.session_state.risk_appetite} / 10</strong>
                            </div>
                            <div>
                                Analys
                                <strong>{st.session_state.analysis_window}</strong>
                            </div>
                        </div>
                        <div class="mock-note">
                            {"Det här är en låst standardprofil med förvalda mål för vikt, Sharpe, volatilitet och drawdown." if not custom_profile_enabled else "Egen profil är aktiv. Här kan du sätta dina egna riskramar och målvikter."}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if not custom_profile_enabled:
                    st.info("Välj Egen profil om du vill låsa upp egna riskmål och egna målvikter.")
                else:
                    st.success("Egen profil är aktiv. Dina ändringar påverkar analysen direkt.")

        with settings_questionnaire_tab:
            questionnaire_result = calculate_risk_questionnaire_profile()
            questionnaire_col, questionnaire_summary_col = st.columns([1.1, 0.9], gap="large")

            with questionnaire_col:
                for question in get_risk_questionnaire():
                    st.selectbox(
                        question["question"],
                        options=[option["label"] for option in question["options"]],
                        key=question["key"],
                    )

            with questionnaire_summary_col:
                st.markdown(
                    f"""
                    <div class="section-card">
                        <strong>Föreslagen risknivå från enkäten</strong>
                        <div class="micro-kpi">
                            <div>
                                Risknivå
                                <strong>{questionnaire_result['risk_level']} / 10</strong>
                            </div>
                            <div>
                                Poäng
                                <strong>{questionnaire_result['score_100']:.0f} / 100</strong>
                            </div>
                            <div>
                                Effekt
                                <strong>Uppdaterar riskmål</strong>
                            </div>
                        </div>
                        <div class="mock-note">
                            Enkäten väger främst in horisont, reaktion på förlust, mål, erfarenhet och likviditetsbehov.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.button(
                    "Använd enkätens risknivå",
                    use_container_width=True,
                    on_click=apply_questionnaire_risk_profile,
                )
                st.caption(
                    "När knappen används sätts både risknivå 1-10 och rekommenderade gränser för Sharpe, volatilitet och drawdown."
                )
                with st.expander("Varför frågorna väger olika mycket"):
                    st.markdown(
                        """
                        - Reaktion på en förlust på 20 % väger tyngst eftersom den ofta säger mest om faktisk riskvilja när marknaden faller.
                        - Placeringshorisont väger nästan lika tungt eftersom längre tidshorisont normalt ger högre riskförmåga.
                        - Mål med sparandet, erfarenhet och likviditetsbehov påverkar också nivån, men bör inte dominera hela profilen på egen hand.
                        """
                    )

        with settings_risk_tab:
            recommended_risk_defaults = get_risk_preference_defaults(int(st.session_state.risk_appetite))
            st.caption(
                f"Rekommenderat för risknivå {st.session_state.risk_appetite}: "
                f"Sharpe minst {format_decimal_sv(recommended_risk_defaults['min_portfolio_sharpe'])}, "
                f"volatilitet max {format_pct(recommended_risk_defaults['max_portfolio_volatility'])}, "
                f"max drawdown {format_pct(recommended_risk_defaults['max_drawdown_tolerance'])}."
            )
            st.button(
                "Använd rekommenderade riskmål",
                use_container_width=False,
                on_click=apply_recommended_risk_targets,
                args=(int(st.session_state.risk_appetite),),
                disabled=not custom_profile_enabled,
            )

            risk_col_left, risk_col_right = st.columns(2, gap="large")
            with risk_col_left:
                st.slider(
                    "Minsta historiska Sharpekvot",
                    min_value=-1.0,
                    max_value=2.0,
                    step=0.05,
                    key="min_portfolio_sharpe",
                    disabled=not custom_profile_enabled,
                )
                st.slider(
                    "Max historisk volatilitet (%)",
                    min_value=1.0,
                    max_value=40.0,
                    step=0.5,
                    key="max_portfolio_volatility",
                    disabled=not custom_profile_enabled,
                )
                st.slider(
                    "Max historisk drawdown (%)",
                    min_value=1.0,
                    max_value=60.0,
                    step=1.0,
                    key="max_drawdown_tolerance",
                    disabled=not custom_profile_enabled,
                )
                st.slider(
                    "Gräns för enskilt innehav",
                    min_value=0,
                    max_value=100,
                    step=1,
                    key="concentration_threshold",
                    disabled=not custom_profile_enabled,
                )

            with risk_col_right:
                st.slider(
                    "Tolerans över aktiemål innan varning (p.p.)",
                    min_value=0,
                    max_value=30,
                    step=1,
                    key="equity_buffer",
                    disabled=not custom_profile_enabled,
                )
                st.slider(
                    "Gräns för avvikelse mot målvikt (p.p.)",
                    min_value=0,
                    max_value=30,
                    step=1,
                    key="category_gap_threshold",
                    disabled=not custom_profile_enabled,
                )
                st.slider(
                    "Gräns för tre största innehav tillsammans",
                    min_value=0,
                    max_value=100,
                    step=1,
                    key="top_three_threshold",
                    disabled=not custom_profile_enabled,
                )
                st.slider(
                    "Minsta köp/sälj som visas",
                    min_value=0,
                    max_value=25000,
                    step=500,
                    key="minimum_trade_size",
                    disabled=not custom_profile_enabled,
                )

        with settings_weight_tab:
            category_instrument_catalog = get_category_instrument_catalog()
            current_target_total = sum(
                float(st.session_state[f"target_weight_{category}"]) for category in category_order
            )
            st.caption(
                f"{'Sätt egna målvikter per kategori och välj vilket verkligt instrument som ska representera varje del.' if custom_profile_enabled else 'Standardprofilen visar sina låsta målvikter och sina förvalda verkliga instrument här.'} "
                f"Summan är just nu {format_pct(current_target_total)} och normaliseras automatiskt till 100 % i analysen."
            )
            weight_cols = st.columns(2, gap="large")
            for index, category in enumerate(category_order):
                with weight_cols[index % 2]:
                    instrument_key = f"category_instrument_{category}"
                    if not custom_profile_enabled:
                        st.session_state[instrument_key] = default_category_instruments[category]
                    st.number_input(
                        category,
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        key=f"target_weight_{category}",
                        disabled=not custom_profile_enabled,
                    )
                    st.selectbox(
                        f"Verkligt instrument för {category}",
                        options=[option["ticker"] for option in category_instrument_catalog[category]],
                        key=instrument_key,
                        format_func=get_category_instrument_label,
                        disabled=not custom_profile_enabled,
                    )
            st.caption(
                "Standardprofilerna använder låsta målvikter och förvalda instrument. Växla till Egen profil om du vill sätta både vikt och instrument själv."
                if not custom_profile_enabled
                else "Din egen profil använder de vikter och instrument du sätter här, och analysen uppdateras direkt."
            )

        if abs(selected_profile_config["raw_weight_total"] - 100) > 0.01:
            st.info(
                f"Du har satt målvikter som summerar till {format_pct(selected_profile_config['raw_weight_total'])}. "
                "Appen normaliserar dem automatiskt till 100 % innan analysen körs."
            )
    st.write("")
    source_col_1, source_col_2, source_col_3 = st.columns(3, gap="large")
    source_col_1.markdown(
        f"""
        <div class="section-card">
            <strong>Portföljöversikt</strong>
            <div class="mock-note">Portföljen följs upp med aktuella värden och historisk utveckling för de innehav som ingår i analysen.</div>
            <div class="micro-kpi">
                <div>
                    Innehav
                    <strong>{len(portfolio)}</strong>
                </div>
                <div>
                    Valuta
                    <strong>USD/SEK</strong>
                </div>
                <div>
                    Källa
                    <strong>Marknadsdata</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    source_col_2.markdown(
        f"""
        <div class="section-card">
            <strong>TestSAVR</strong>
            <div class="mock-note">Samma urval av instrument kan användas för bevakning, bakåtblick och framtidsscenarier.</div>
            <div class="micro-kpi">
                <div>
                    Instrument
                    <strong>{len(instrument_universe)}</strong>
                </div>
                <div>
                    Aktier / ETF:er
                    <strong>{len(watchlist)} / {len(portfolio)}</strong>
                </div>
                <div>
                    Källa
                    <strong>Marknadsdata</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    source_col_3.markdown(
        f"""
        <div class="section-card">
            <strong>Fondinformation</strong>
            <div class="mock-note">Fondöversikten kompletteras med information från SAVR:s fondutbud.</div>
            <div class="micro-kpi">
                <div>
                    Fonder
                    <strong>{len(savr_fund_catalog)}</strong>
                </div>
                <div>
                    ISIN
                    <strong>{savr_fund_catalog['isin'].nunique() if not savr_fund_catalog.empty else 0}</strong>
                </div>
                <div>
                    Källa
                    <strong>SAVR</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if analysis_history.empty:
        st.warning("Kunde inte hämta prisdata just nu. Riskanalysen och TestSAVR kan bli tomma tills marknadsdata laddas.")

    if active_module == "Rebalansering":
        st.write("")
        metric_cols = st.columns(5)
        metric_cols[0].metric("Portföljvärde", format_sek(metrics["total_value"]))
        metric_cols[1].metric(
            "Aktieexponering",
            format_pct(metrics["equity_exposure"]),
            delta=f"{format_decimal_sv(metrics['equity_gap'], decimals=2, signed=True)} p.p. mot profil",
        )
        metric_cols[2].metric(
            "Historisk Sharpe",
            format_decimal_sv(metrics["portfolio_sharpe"]),
            delta=f"Mål {format_decimal_sv(st.session_state.min_portfolio_sharpe)}",
        )
        metric_cols[3].metric(
            "Historisk volatilitet",
            format_pct(metrics["portfolio_volatility_pct"]),
            delta=f"Tak {format_pct(st.session_state.max_portfolio_volatility)}",
        )
        metric_cols[4].metric(
            "Största innehav",
            metrics["largest_name"],
            delta=format_pct(metrics["largest_weight_pct"]),
        )

        st.write("")
        left_col, right_col = st.columns([1.05, 1], gap="large")

        with left_col:
            st.subheader("Din portfölj idag")
            st.caption("Översikten visar hur kapitalet är fördelat just nu.")
            display_df = portfolio_df[
                [
                    "name",
                    "ticker",
                    "category",
                    "value_sek",
                    "current_weight_pct",
                    "trailing_1m_pct",
                    "annual_volatility_pct",
                    "sharpe_ratio",
                ]
            ].copy()
            display_df.columns = [
                "Fond",
                "Ticker",
                "Kategori",
                "Värde",
                "Vikt",
                "1 mån",
                "Volatilitet",
                "Sharpe",
            ]
            display_df["Värde"] = display_df["Värde"].map(format_sek)
            display_df["Vikt"] = display_df["Vikt"].map(format_pct)
            display_df["1 mån"] = display_df["1 mån"].map(format_signed_pct)
            display_df["Volatilitet"] = display_df["Volatilitet"].map(format_pct)
            display_df["Sharpe"] = display_df["Sharpe"].map(lambda x: f"{x:.2f}".replace(".", ","))
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        with right_col:
            st.subheader("Nuvarande viktfördelning")
            st.caption("Donut-grafen gör det lätt att se var portföljen domineras av några få teman.")
            st.plotly_chart(build_current_allocation_chart(portfolio_df), use_container_width=True)

    if active_module == "Rebalansering":
        st.write("")
        insight_col, support_col = st.columns([1.1, 0.9], gap="large")

        with insight_col:
            st.subheader("Vad Portföljkollen ser")
            render_insights(insights)

        with support_col:
            st.subheader("Snabb diagnos")
            st.markdown(
                f"""
                <div class="panel">
                    <strong>Största tre innehav:</strong> {format_pct(metrics["top_three_share"])}<br><br>
                    <strong>Koncentrationsindex:</strong> {metrics["hhi"]}<br><br>
                    <strong>Historisk avkastning:</strong> {format_signed_pct(metrics["portfolio_return_pct"])}<br><br>
                    <strong>Historisk drawdown:</strong> {format_pct(abs(metrics["portfolio_max_drawdown_pct"]))}<br><br>
                    <strong>Din gräns för största innehav:</strong> {selected_profile_config["max_single_holding"]} %<br><br>
                    <strong>Min Sharpe / Max vol:</strong> {format_decimal_sv(st.session_state.min_portfolio_sharpe)} / {format_pct(st.session_state.max_portfolio_volatility)}<br><br>
                    <strong>Tolkning:</strong> Analysen följer dina egna trösklar, dina egna målvikter och historisk marknadsutveckling.
                </div>
                """,
                unsafe_allow_html=True,
            )

    if active_module == "Rebalansering":
        st.write("")
        st.subheader("Föreslagen målallokering")
        st.caption(
            "Den föreslagna fördelningen bygger på dina egna målvikter och översätts direkt till kronor att köpa eller sälja."
        )
        st.plotly_chart(build_comparison_chart(portfolio_df), use_container_width=True)

        trade_display = trade_plan[
            [
                "name",
                "category",
                "current_weight_pct",
                "target_weight_pct",
                "trade_action",
                "trade_amount",
            ]
        ].copy()
        trade_display.columns = [
            "Fond",
            "Kategori",
            "Nuvarande vikt",
            "Målvikt",
            "Åtgärd",
            "Belopp",
        ]
        trade_display["Nuvarande vikt"] = trade_display["Nuvarande vikt"].map(format_pct)
        trade_display["Målvikt"] = trade_display["Målvikt"].map(format_pct)
        trade_display["Belopp"] = trade_display["Belopp"].map(format_sek)
        if trade_display.empty:
            st.info(
                "Inga köp eller sälj visas just nu eftersom alla avvikelser ligger under din valda gräns för minsta affär."
            )
        else:
            st.dataframe(trade_display, use_container_width=True, hide_index=True)

        largest_sell = trade_plan.loc[trade_plan["trade_action"] == "Sälj"].head(1)
        largest_buy = trade_plan.loc[trade_plan["trade_action"] == "Köp"].head(1)
        if not largest_sell.empty and not largest_buy.empty:
            sell_row = largest_sell.iloc[0]
            buy_row = largest_buy.iloc[0]
            st.info(
                f"Förslag: minska {sell_row['name']} med {format_sek(sell_row['trade_amount'])} "
                f"och öka {buy_row['name']} med {format_sek(buy_row['trade_amount'])} som första steg."
            )
        elif trade_display.empty:
            st.info("Portföljen ligger nära dina egna mål eller så har du filtrerat bort små affärer.")

    if active_module == "Rebalansering":
        st.write("")
        st.subheader("Pushnotiser och bevakning")
        st.caption(
            "Notisflödet visar exempel på bevakningsnotiser och rebalanseringspåminnelser baserade på portföljens utveckling."
        )

        watch_tab, rebalance_tab = st.tabs(["Bevakade instrument", "Rebalanseringspåminnelse"])

        with watch_tab:
            watch_control_col, watch_feed_col = st.columns([0.95, 1.05], gap="large")

            with watch_control_col:
                watch_selection = st.multiselect(
                    "Vilka instrument vill du bevaka?",
                    options=instrument_universe["company_name"].tolist(),
                    default=st.session_state.watch_selection,
                )
                watch_interval = st.selectbox(
                    "Hur ofta vill du få uppdateringar?",
                    options=list(notification_intervals.keys()),
                    index=list(notification_intervals.keys()).index(st.session_state.watch_interval),
                )
                watch_notifications = build_watch_notifications(
                    instrument_universe, full_price_history, watch_selection, watch_interval
                )

                activate_watch = st.button("Aktivera bevakning", use_container_width=True)
                test_watch = st.button("Skicka testnotiser nu", use_container_width=True)

                if activate_watch:
                    st.session_state.watch_selection = watch_selection
                    st.session_state.watch_interval = watch_interval
                    st.session_state.watch_active = True
                    st.toast(
                        f"Bevakning aktiv för {len(watch_selection)} instrument med intervallet {watch_interval.lower()}."
                    )

                if test_watch and not watch_notifications.empty:
                    for _, row in watch_notifications.head(3).iterrows():
                        st.toast(row["notification_text"])

                st.markdown(
                    f"""
                    <div class="panel">
                        <strong>Status:</strong> {"Aktiv" if st.session_state.watch_active else "Inte aktiv"}<br><br>
                        <strong>Nästa utskick:</strong> {format_date_sv((watch_notifications["next_send_at"].iloc[0] if not watch_notifications.empty else pd.Timestamp.today()))}<br><br>
                        <strong>Intervall:</strong> {watch_interval}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with watch_feed_col:
                if not watch_notifications.empty:
                    watch_display = watch_notifications[
                        [
                            "company_name",
                            "ticker",
                            "position_value_sek",
                            "current_price",
                            "change_pct",
                            "notification_text",
                        ]
                    ].copy()
                    watch_display.columns = [
                        "Instrument",
                        "Ticker",
                        "Bevakat värde",
                        "Senaste kurs",
                        f"Förändring sedan {notification_intervals[watch_interval]['reference_text']}",
                        "Exempel på notis",
                    ]
                    watch_display["Bevakat värde"] = watch_display["Bevakat värde"].map(format_sek)
                    watch_display["Senaste kurs"] = watch_display["Senaste kurs"].map(
                        lambda x: f"{x:,.2f}".replace(",", " ").replace(".", ",")
                    )
                    change_column = f"Förändring sedan {notification_intervals[watch_interval]['reference_text']}"
                    watch_display[change_column] = watch_display[change_column].map(format_signed_pct)
                    st.dataframe(watch_display, use_container_width=True, hide_index=True)
                else:
                    st.info("Välj minst ett instrument för att skapa notiser.")

                watch_messages = []
                for _, row in watch_notifications.head(3).iterrows():
                    watch_messages.append(
                        {
                            "title": f"{row['company_name']} ({row['ticker']})",
                            "body": row["notification_text"],
                        }
                    )
                render_notification_cards("Förhandsvisning av pushnotiser", watch_messages, tone="info")

        with rebalance_tab:
            rebalance_control_col, rebalance_feed_col = st.columns([0.95, 1.05], gap="large")

            with rebalance_control_col:
                rebalance_interval = st.selectbox(
                    "När vill du få påminnelse om rebalansering?",
                    options=list(notification_intervals.keys()),
                    index=list(notification_intervals.keys()).index(st.session_state.rebalance_interval),
                    key="rebalance_interval_selector",
                )
                rebalance_notification = build_rebalance_notification(
                    portfolio_df, trade_plan, selected_profile_name, rebalance_interval
                )

                activate_rebalance = st.button(
                    "Aktivera rebalanseringspåminnelse", use_container_width=True
                )
                test_rebalance = st.button("Skicka testpåminnelse nu", use_container_width=True)

                if activate_rebalance:
                    st.session_state.rebalance_interval = rebalance_interval
                    st.session_state.rebalance_active = True
                    st.toast(
                    f"Rebalanseringspåminnelse sparad med intervallet {rebalance_interval.lower()}."
                    )

                if test_rebalance:
                    st.toast(rebalance_notification["short_text"])

                st.markdown(
                    f"""
                    <div class="panel">
                        <strong>Status:</strong> {"Aktiv" if st.session_state.rebalance_active else "Inte aktiv"}<br><br>
                        <strong>Nästa utskick:</strong> {format_date_sv(rebalance_notification["next_send_at"])}<br><br>
                        <strong>Profil:</strong> {selected_profile_name}<br><br>
                        <strong>Syfte:</strong> Påminna när portföljen glidit från målvikterna.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with rebalance_feed_col:
                drift_display = portfolio_df[
                    [
                        "name",
                        "current_weight_pct",
                        "target_weight_pct",
                        "weight_gap_pct",
                        "trailing_1m_pct",
                    ]
                ].copy()
                drift_display.columns = [
                    "Innehav",
                    "Nuvarande vikt",
                    "Målvikt",
                    "Avvikelse mot mål",
                    "Senaste månaden",
                ]
                drift_display["Nuvarande vikt"] = drift_display["Nuvarande vikt"].map(format_pct)
                drift_display["Målvikt"] = drift_display["Målvikt"].map(format_pct)
                drift_display["Avvikelse mot mål"] = drift_display["Avvikelse mot mål"].map(
                    format_signed_pct
                )
                drift_display["Senaste månaden"] = drift_display["Senaste månaden"].map(
                    format_signed_pct
                )
                st.dataframe(drift_display, use_container_width=True, hide_index=True)

                render_notification_cards(
                    "Förhandsvisning av rebalanseringsnotis",
                    [
                        {
                            "title": rebalance_notification["title"],
                            "body": rebalance_notification["body"],
                        }
                    ],
                    tone="warning",
                )

    if active_module == "TestSAVR":
        st.write("")
        st.subheader("TestSAVR")
        st.caption(
            "Prova hur ett belopp hade utvecklats över tid och hur olika fördelningar och rebalanseringar kan påverka framtida utfall."
        )
        portfolio_simulation_assets = portfolio_df["name"].tolist()
        portfolio_simulation_weights = {
            row["name"]: float(row["current_weight_pct"])
            for _, row in portfolio_df[["name", "current_weight_pct"]].iterrows()
        }

        mock_source = st.radio(
            "Vad vill du simulera?",
            options=["Egna instrument", "Portfölj från Portföljkollen"],
            index=0 if st.session_state.mock_source == "Egna instrument" else 1,
            horizontal=True,
        )
        st.session_state.mock_source = mock_source

        if mock_source == "Egna instrument":
            mock_assets = st.multiselect(
                "Vilka instrument ska ingå i simuleringen?",
                options=instrument_universe["company_name"].tolist(),
                default=st.session_state.mock_assets,
            )
            st.session_state.mock_assets = mock_assets
        else:
            mock_assets = portfolio_simulation_assets
            st.info(
                "TestSAVR använder nu samma innehav som i Portföljkollen. Du kan därmed granska den aktuella portföljen både bakåt i tiden och i framtidssimuleringen."
            )
            portfolio_selection_display = portfolio_df[
                ["name", "ticker", "current_weight_pct"]
            ].copy()
            portfolio_selection_display.columns = [
                "Innehav från Portföljkollen",
                "Ticker",
                "Nuvarande vikt",
            ]
            portfolio_selection_display["Nuvarande vikt"] = portfolio_selection_display[
                "Nuvarande vikt"
            ].map(format_pct)
            st.dataframe(portfolio_selection_display, use_container_width=True, hide_index=True)

        mock_config_col, mock_summary_col = st.columns([1.1, 0.9], gap="large")
        with mock_config_col:
            mock_amount = st.slider(
                "Belopp för simuleringen",
                min_value=1000,
                max_value=100000,
                value=st.session_state.mock_amount,
                step=1000,
            )
            st.session_state.mock_amount = mock_amount

            available_weight_modes = ["Likavikt", "Anpassad"]
            if mock_source == "Portfölj från Portföljkollen":
                available_weight_modes = ["Nuvarande portföljvikter", *available_weight_modes]
            if st.session_state.mock_weight_mode not in available_weight_modes:
                st.session_state.mock_weight_mode = available_weight_modes[0]
            mock_weight_mode = st.radio(
                "Hur ska beloppet fördelas?",
                options=available_weight_modes,
                index=available_weight_modes.index(st.session_state.mock_weight_mode),
                horizontal=True,
            )
            st.session_state.mock_weight_mode = mock_weight_mode
            rebalance_modes = list(get_mock_rebalance_modes().keys())
            mock_rebalance_mode = st.radio(
                "Hur ska portföljen hanteras över tid?",
                options=rebalance_modes,
                index=rebalance_modes.index(st.session_state.mock_rebalance_mode),
                horizontal=True,
            )
            st.session_state.mock_rebalance_mode = mock_rebalance_mode
            st.caption(get_mock_rebalance_modes()[mock_rebalance_mode]["description"])

            raw_mock_weights = {}
            if mock_weight_mode == "Nuvarande portföljvikter":
                raw_mock_weights = portfolio_simulation_weights.copy()
                st.caption(
                    "Beloppet fördelas efter de nuvarande vikterna i Portföljkollen, så att TestSAVR kan användas för att analysera samma portföljhistorik och framtidsscenarier."
                )
            elif mock_weight_mode == "Likavikt":
                raw_mock_weights = {asset: 1.0 for asset in mock_assets}
            else:
                st.markdown("**Sätt egen vikt per instrument**")
                for asset in mock_assets:
                    weight_key = f"mock_weight_{asset}"
                    if weight_key not in st.session_state:
                        st.session_state[weight_key] = 100 / max(len(mock_assets), 1)
                    raw_mock_weights[asset] = st.number_input(
                        asset,
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        key=weight_key,
                    )

            allocation_preview = {}
            raw_mock_total = 0.0
            if raw_mock_weights:
                allocation_preview, raw_mock_total = normalize_target_weights(raw_mock_weights)

            if mock_weight_mode == "Anpassad" and raw_mock_weights:
                st.caption(
                    f"Egen vikt summerar till {format_pct(raw_mock_total)}. Appen normaliserar automatiskt till 100 %."
                )

        with mock_summary_col:
            preview_items = "".join(
                [
                    f"<div><span>{asset}</span><strong>{format_pct(weight)}</strong></div>"
                    for asset, weight in allocation_preview.items()
                ]
            )
            st.markdown(
                f"""
                <div class="section-card">
                    <strong>Upplägg för TestSAVR</strong>
                    <div class="micro-kpi">
                        <div>
                            Belopp
                            <strong>{format_sek(mock_amount)}</strong>
                        </div>
                        <div>
                            Källa
                            <strong>{mock_source}</strong>
                        </div>
                        <div>
                            Antal instrument
                            <strong>{len(mock_assets)}</strong>
                        </div>
                        <div>
                            Rebalansering
                            <strong>{mock_rebalance_mode}</strong>
                        </div>
                    </div>
                    <div class="micro-kpi">
                        {preview_items if preview_items else '<div><span>Välj minst ett instrument</span><strong>0,0 %</strong></div>'}
                    </div>
                    <div class="mock-note">
                        Översikten visar hur beloppet fördelas och hur vald rebalanseringslogik påverkar utvecklingen över tid.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        max_backtest_date = max(history_first_date, history_last_date - pd.Timedelta(days=1))
        min_future_date = (history_last_date + pd.offsets.BDay(1)).normalize()
        max_future_date = history_last_date + pd.DateOffset(years=3)
        mock_history_tab, mock_future_tab = st.tabs(["Bakåtblick", "Framåtblick"])

        with mock_history_tab:
            backtest_mode = st.selectbox(
                "Bakåtblick: välj startpunkt",
                options=["Snabbval", "Eget datum"],
                key="mock_backtest_mode",
            )
            if backtest_mode == "Snabbval":
                backtest_interval = st.selectbox(
                    "Period",
                    options=list(get_mock_backtest_intervals().keys()),
                    key="mock_backtest_interval",
                )
                backtest_custom_start = None
            else:
                backtest_calendar_value = pd.Timestamp(st.session_state.mock_backtest_custom_date).normalize()
                if backtest_calendar_value < history_first_date:
                    backtest_calendar_value = history_first_date
                if backtest_calendar_value > max_backtest_date:
                    backtest_calendar_value = max_backtest_date
                backtest_calendar = st.date_input(
                    "Välj startdatum",
                    value=backtest_calendar_value.date(),
                    min_value=history_first_date.date(),
                    max_value=max_backtest_date.date(),
                    format="DD/MM/YYYY",
                    key="mock_backtest_custom_date",
                )
                st.text_input(
                    "Eller skriv datum (ddmmyyyy)",
                    key="mock_backtest_custom_text",
                    placeholder="01032025",
                )
                backtest_custom_start, backtest_text_valid = resolve_input_date(
                    backtest_calendar, st.session_state.mock_backtest_custom_text
                )
                if st.session_state.mock_backtest_custom_text.strip() and not backtest_text_valid:
                    st.warning("Kunde inte tolka datumet. Skriv det som ddmmyyyy, till exempel 01032025.")
                backtest_interval = st.session_state.mock_backtest_interval

            if backtest_mode == "Eget datum" and (
                backtest_custom_start is None
                or backtest_custom_start < history_first_date
                or backtest_custom_start >= history_last_date
            ):
                backtest_df, backtest_summary = pd.DataFrame(), {}
            else:
                backtest_df, backtest_summary = simulate_mock_backtest(
                    instrument_universe,
                    full_price_history,
                    mock_assets,
                    mock_amount,
                    raw_mock_weights,
                    backtest_interval,
                    custom_start_date=backtest_custom_start,
                    rebalance_mode=mock_rebalance_mode,
                )

            if backtest_df.empty:
                if not mock_assets:
                    st.info("Välj minst ett instrument för att köra simuleringen bakåt i tiden.")
                elif backtest_mode == "Eget datum" and (
                    backtest_custom_start is None
                    or backtest_custom_start < history_first_date
                    or backtest_custom_start >= history_last_date
                ):
                    st.info("Välj ett giltigt startdatum för att köra simuleringen bakåt i tiden.")
                else:
                    st.info("Kunde inte hämta tillräcklig historik för de valda instrumenten just nu. Prova att uppdatera sidan eller välj ett annat urval.")
            else:
                st.success(
                    f"Om du hade investerat {format_sek(mock_amount)} {backtest_summary['reference_text']}, "
                    f"med {backtest_summary['rebalance_mode_label']}, hade portföljen varit värd {format_sek(backtest_summary['current_value'])} idag "
                    f"({format_signed_pct(backtest_summary['return_pct'])})."
                )
                if backtest_summary["rebalance_count"] > 0:
                    st.caption(
                        f"Portföljen återställdes mot målvikterna {backtest_summary['rebalance_count']} gånger under perioden."
                    )

                backtest_cols = st.columns([1.05, 0.95], gap="large")
                with backtest_cols[0]:
                    st.plotly_chart(
                        build_mock_backtest_chart(
                            backtest_summary["history_series"],
                            backtest_summary["invested_amount"],
                        ),
                        use_container_width=True,
                    )
                with backtest_cols[1]:
                    history_display = backtest_df[
                        [
                            "company_name",
                            "allocation_pct",
                            "investment_amount",
                            "value_today",
                            "return_pct",
                        ]
                    ].copy()
                    history_display.columns = [
                        "Instrument",
                        "Fördelning",
                        "Investerat då",
                        "Värde idag",
                        "Avkastning",
                    ]
                    history_display["Fördelning"] = history_display["Fördelning"].map(format_pct)
                    history_display["Investerat då"] = history_display["Investerat då"].map(format_sek)
                    history_display["Värde idag"] = history_display["Värde idag"].map(format_sek)
                    history_display["Avkastning"] = history_display["Avkastning"].map(format_signed_pct)
                    st.dataframe(history_display, use_container_width=True, hide_index=True)

        with mock_future_tab:
            future_mode = st.selectbox(
                "Framåtblick: välj slutpunkt",
                options=["Snabbval", "Eget datum"],
                key="mock_future_mode",
            )
            if future_mode == "Snabbval":
                future_horizon = st.selectbox(
                    "Scenariohorisont",
                    options=list(get_mock_future_horizons().keys()),
                    key="mock_future_horizon",
                )
                future_custom_end = None
            else:
                future_calendar_value = pd.Timestamp(st.session_state.mock_future_custom_date).normalize()
                if future_calendar_value < min_future_date:
                    future_calendar_value = min_future_date
                if future_calendar_value > max_future_date:
                    future_calendar_value = max_future_date
                future_calendar = st.date_input(
                    "Välj slutdatum",
                    value=future_calendar_value.date(),
                    min_value=min_future_date.date(),
                    max_value=max_future_date.date(),
                    format="DD/MM/YYYY",
                    key="mock_future_custom_date",
                )
                st.text_input(
                    "Eller skriv datum (ddmmyyyy)",
                    key="mock_future_custom_text",
                    placeholder="01122026",
                )
                future_custom_end, future_text_valid = resolve_input_date(
                    future_calendar, st.session_state.mock_future_custom_text
                )
                if st.session_state.mock_future_custom_text.strip() and not future_text_valid:
                    st.warning("Kunde inte tolka datumet. Skriv det som ddmmyyyy, till exempel 01122026.")
                elif future_custom_end is not None and future_custom_end <= history_last_date:
                    st.warning(
                        f"Framtidsdatum måste ligga efter senaste historikdag. Välj tidigast {format_date_sv(min_future_date)}."
                    )
                future_horizon = st.session_state.mock_future_horizon

            if future_mode == "Eget datum" and (
                future_custom_end is None or future_custom_end <= history_last_date
            ):
                future_asset_df, future_summary_df, future_path_df, future_summary = (
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    {},
                )
            else:
                future_asset_df, future_summary_df, future_path_df, future_summary = simulate_mock_future(
                    instrument_universe,
                    full_price_history,
                    mock_assets,
                    mock_amount,
                    raw_mock_weights,
                    future_horizon,
                    custom_end_date=future_custom_end,
                    rebalance_mode=mock_rebalance_mode,
                )

            if future_asset_df.empty or future_summary_df.empty or future_path_df.empty:
                if not mock_assets:
                    st.info("Välj minst ett instrument för att skapa bootstrap-baserade simuleringar.")
                elif future_mode == "Eget datum" and (
                    future_custom_end is None or future_custom_end <= history_last_date
                ):
                    st.info("Välj ett giltigt framtidsdatum för att skapa bootstrap-baserade simuleringar.")
                else:
                    st.info("Kunde inte skapa simuleringen med de valda instrumenten just nu. Prova att uppdatera sidan eller välj en annan horisont.")
            else:
                st.info(
                    f"Medianutfallet {future_summary['label']} är {format_sek(future_summary['median_value'])} "
                    f"({format_signed_pct(future_summary['median_return_pct'])}). "
                    f"I 80 % av bootstrap-simuleringarna ligger slutvärdet mellan {format_sek(future_summary['p10_value'])} "
                    f"och {format_sek(future_summary['p90_value'])} med {future_summary['rebalance_mode_label']}. Sannolikheten för plus är "
                    f"{format_pct(future_summary['probability_positive_pct'])}."
                )
                if future_summary["rebalance_count"] > 0:
                    st.caption(
                        f"I den valda horisonten återställs portföljen mot målvikterna ungefär {future_summary['rebalance_count']} gånger per simulering."
                    )

                future_cols = st.columns([0.9, 1.1], gap="large")
                with future_cols[0]:
                    st.plotly_chart(
                        build_mock_future_chart(future_path_df, mock_amount),
                        use_container_width=True,
                    )
                with future_cols[1]:
                    future_display = future_asset_df[
                        [
                            "company_name",
                            "allocation_pct",
                            "Nedre spann (P10)",
                            "Median (P50)",
                            "Övre spann (P90)",
                        ]
                    ].copy()
                    future_display.columns = [
                        "Instrument",
                        "Fördelning",
                        "Nedre spann (P10)",
                        "Median (P50)",
                        "Övre spann (P90)",
                    ]
                    future_display["Fördelning"] = future_display["Fördelning"].map(format_pct)
                    future_display["Nedre spann (P10)"] = future_display[
                        "Nedre spann (P10)"
                    ].map(format_signed_pct)
                    future_display["Median (P50)"] = future_display["Median (P50)"].map(
                        format_signed_pct
                    )
                    future_display["Övre spann (P90)"] = future_display["Övre spann (P90)"].map(
                        format_signed_pct
                    )
                    st.dataframe(future_display, use_container_width=True, hide_index=True)
                    st.caption(
                        f"Simuleringen bygger på {future_summary['simulations']} bootstrap-vägar med blockstorlek {future_summary['block_size']} handelsdagar."
                    )

    if active_module == "Rebalansering":
        st.write("")
        st.subheader("Ny insättning")
        st.caption(
            "Simulera hur en ny insättning kan användas för att minska obalansen utan att du behöver sälja direkt."
        )

        extra_contribution = st.slider(
            "Extra insättning",
            min_value=1000,
            max_value=20000,
            value=5000,
            step=1000,
        )
        contribution_df = simulate_contribution(portfolio_df, extra_contribution)
        buy_gap = portfolio_df.loc[portfolio_df["trade_value"] > 0, "trade_value"].sum()
        funded_share = min(extra_contribution / buy_gap, 1) * 100 if buy_gap else 100

        contribution_cols = st.columns([1, 1], gap="large")
        with contribution_cols[0]:
            st.plotly_chart(build_contribution_chart(contribution_df), use_container_width=True)
        with contribution_cols[1]:
            cash_plan = contribution_df.loc[contribution_df["cash_allocation"] >= 500].copy()
            cash_plan = cash_plan.sort_values("cash_allocation", ascending=False)
            cash_display = cash_plan[["name", "cash_allocation", "weight_after_cash_pct"]].copy()
            cash_display.columns = ["Fond", "Föreslagen insättning", "Vikt efter insättning"]
            cash_display["Föreslagen insättning"] = cash_display["Föreslagen insättning"].map(format_sek)
            cash_display["Vikt efter insättning"] = cash_display["Vikt efter insättning"].map(format_pct)
            st.dataframe(cash_display, use_container_width=True, hide_index=True)
            st.success(
                f"En insättning på {format_sek(extra_contribution)} kan finansiera ungefär "
                f"{format_pct(funded_share)} av de köp som behövs för att närma dig målportföljen."
            )

    with st.expander("Så beräknas analysen"):
        st.markdown(
            """
            - Portföljvärdena beräknas från marknadspriser och USD/SEK-kurser via Yahoo Finance.
            - Riskanalysen använder historisk avkastning, volatilitet, max drawdown och Sharpekvot över valt analysfönster.
            - Riskbenägenhet 1-10 är en heuristisk skala som översätts till mål för Sharpe, volatilitet och drawdown.
            - Rebalanseringen jämför nuvarande vikter mot dina egna målvikter, riskgränser och Sharpe-/volmål.
            - Köp- och säljförslag visas i kronor för att göra förändringarna lätta att förstå och jämföra.
            - Sektionen för ny insättning använder nytt kapital först på de delar som ligger under målvikten.
            - Bevakade instrument använder verkliga historiska prisförändringar för olika intervall och visar hur en pushnotis kan formuleras.
            - Rebalanseringspåminnelsen visar när portföljen avviker från vald profil och vilka förändringar som kan krävas för att återgå till målvikterna.
            - TestSAVR räknar bakåt med riktig historik och framåt med bootstrap-baserad Monte Carlo som återanvänder historiska returblock. Metoden ger ett pedagogiskt sannolikhetsspann, men modellerar inte explicit tidsvarierande volatilitet eller volatilitetklustring. Prognosprecisionen kan därför förbättras genom att ersätta eller komplettera simuleringen med en mer avancerad volatilitetsspecifikation, exempelvis en GARCH-inspirerad modell.
            - I TestSAVR kan du välja mellan buy and hold, månadsvis rebalansering och kvartalsvis rebalansering för att se hur målvikter påverkar utvecklingen över tid.
            - Både bakåtblick och framåtblick kan styras med snabbval eller egna datum via kalender och manuell inmatning i formatet ddmmyyyy.
            - SAVR:s publika fondkatalog används för fondmetadata, medan tidsserierna hämtas från marknadsdata via Yahoo Finance.
            """
        )


if __name__ == "__main__":
    main()
