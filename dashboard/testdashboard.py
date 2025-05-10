import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, dash_table, Input, Output

# ─ Data loading & prep ─
sprint_versions = ["1.0", "1.1", "1.2", "1.3", "1.4"]

# Performance CSVs
dfs = []
for v in sprint_versions:
    df_s = pd.read_csv(f"test_report_data/sprint{v}.csv")
    df_s["sprint"] = f"Sprint {v}"
    dfs.append(df_s)
df_all = pd.concat(dfs, ignore_index=True)
df_all["timestamp"] = pd.to_datetime(df_all["timeStamp"], unit="ms")

# UAT CSVs
uat_dfs = []
for v in sprint_versions:
    uat = pd.read_csv(f"test_report_data/uatSprint{v}.csv")
    uat["sprint"] = f"Sprint {v}"
    uat_dfs.append(uat)
uat_all = pd.concat(uat_dfs, ignore_index=True)

# Bug data from Excel
excel_path = "test_report_data/Test Report Nordic Airlines.xlsx"
bugs_df = pd.read_excel(
    excel_path, sheet_name="Open bugs and defects", skiprows=3
)
bugs_df.columns = [
    "Issue ID", "Description", "Priority",
    "Open date", "Status", "Discovered in", "Link"
]

# Make links clickable
def make_clickable(link, issue_id):
    base = str(link).strip()
    if pd.notna(base) and not base.startswith("http"):
        base = f"https://{base}/browse/{issue_id}"
    return f"[Open Link]({base})" if base.startswith("http") else ""
bugs_df["Link"] = bugs_df.apply(
    lambda r: make_clickable(r["Link"], r["Issue ID"]), axis=1
)

# Sort by Priority (Critical → Medium → Low)
priority_map = {"Critical": 0, "Medium": 1, "Low": 2}
bugs_df["__prio_order"] = bugs_df["Priority"].map(priority_map)
bugs_df.sort_values("__prio_order", inplace=True)
bugs_df.drop(columns="__prio_order", inplace=True)

# Reformat "Open date" to DD-MM-YYYY
bugs_df["Open date"] = pd.to_datetime(bugs_df["Open date"]).dt.strftime("%d-%m-%Y")

# Sprint summaries from Excel
sprint_sheet_names = [f"Sprint {v}" for v in sprint_versions]
sprint_summaries = {}
for sheet in sprint_sheet_names:
    df_s = pd.read_excel(
        excel_path, sheet_name=sheet, skiprows=3
    ).iloc[:, 1:7]
    df_s.columns = [
        "Module", "User Story", "Number of TCs",
        "% TCs Passed", "Number of bugs", "LOC"
    ]
    df_s["% TCs Passed"] = pd.to_numeric(
        df_s["% TCs Passed"].astype(str)
             .str.replace("%", "").str.strip(),
        errors="coerce"
    )
    df_s.loc[df_s["% TCs Passed"] <= 1, "% TCs Passed"] *= 100
    sprint_summaries[sheet] = df_s

summary_df = pd.DataFrame([
    {
        "Sprint": sheet,
        "Total TCs": df_s["Number of TCs"].sum(),
        "% TCs Passed": df_s["% TCs Passed"].mean(),
        "Total Bugs": df_s["Number of bugs"].sum(),
        "Total LOC": df_s["LOC"].sum()
    }
    for sheet, df_s in sprint_summaries.items()
]).sort_values("Sprint")

def compute_stats(df_s):
    grp = df_s.groupby("label").agg({
        "elapsed": "mean",
        "success": lambda x: x.value_counts().to_dict()
    }).reset_index()
    def unpack(r):
        s = r["success"]
        return pd.Series({
            "success_count": s.get(True, 0),
            "failure_count": s.get(False, 0)
        })
    up = grp.apply(unpack, axis=1)
    out = pd.concat([grp.drop(columns="success"), up], axis=1)
    out.rename(columns={"elapsed": "avg_response_time_ms"}, inplace=True)
    return out

# Use dark theme for all Plotly charts
px.defaults.template = "plotly_dark"

# ─ Build Dash app with Darkly Bootstrap ─
external_css = ["https://stackpath.bootstrapcdn.com/bootswatch/4.5.2/darkly/bootstrap.min.css"]
app = Dash(__name__, external_stylesheets=external_css)

card_style = {
    "border": "1px solid #444",
    "borderRadius": "6px",
    "padding": "15px",
    "backgroundColor": "#2a2a2a",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.5)",
    "color": "#fff"
}

app.layout = html.Div(
    style={
        "maxWidth": "1200px",
        "margin": "0 auto",
        "padding": "20px",
        "backgroundColor": "#111",
        "color": "#eee"
    },
    children=[
        html.H1(
            "📊 Software Test Report Dashboard",
            style={"marginBottom": "20px", "fontWeight": "300", "color": "#fff"},
        ),

        # ─ Bugs Table (Status removed) ─
        html.Div(style=card_style, children=[
            html.H4("🐞 Currently Open Bugs and Defects", style={"color": "#fff"}),
            dash_table.DataTable(
                id="bug-table",
                columns=[
                    {"name": "Issue ID", "id": "Issue ID"},
                    {"name": "Description", "id": "Description"},
                    {"name": "Priority", "id": "Priority"},
                    {"name": "Open date", "id": "Open date"},
                    {"name": "Discovered in", "id": "Discovered in"},
                    {"name": "Link", "id": "Link", "presentation": "markdown"},
                ],
                data=bugs_df.to_dict("records"),
                page_size=5,
                page_action="native",
                style_header={
                    "backgroundColor": "#333",
                    "fontWeight": "bold",
                    "color": "#fff"
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#2e2e2e"}
                ],
                style_table={"overflowX": "auto"},
                style_cell={
                    "textAlign": "left",
                    "whiteSpace": "normal",
                    "height": "auto",
                    "backgroundColor": "#2a2a2a",
                    "color": "#ddd"
                },
                markdown_options={"html": False},
            )
        ]),

        html.Div(style={"height": "20px"}),

        # ─ Controls & Key Stats ─
        html.Div(
            style={**card_style, "display": "flex", "gap": "20px", "alignItems": "center"},
            children=[
                html.Div(style={"flex": "1", "maxWidth": "300px"}, children=[
                    html.Label("Select Sprint:", style={"color": "#ddd"}),
                    dcc.Dropdown(
                        id="sprint-selector",
                        options=[{"label": s, "value": s} for s in sprint_sheet_names],
                        value="Sprint 1.4",
                        clearable=False,
                        style={"backgroundColor": "#ffffff", "color": "#000000"}
                    ),
                ]),
                html.Div(style={"flex": "2", "display": "flex", "justifyContent": "space-around"}, children=[
                    html.Div(children=[
                        html.H5("✅ Pass Rate", style={"color": "#28a745"}),
                        html.H3(id="pass-rate")
                    ]),
                    html.Div(children=[
                        html.H5("❌ Bugs", style={"color": "#dc3545"}),
                        html.H3(id="bug-count")
                    ]),
                    html.Div(children=[
                        html.H5("📈 LOC", style={"color": "#17a2b8"}),
                        html.H3(id="loc-count")
                    ]),
                ])
            ]
        ),

        html.Div(style={"height": "20px"}),

        # ─ Cluster A: Severity & UAT & Performance ─
        html.Div(style={"display": "flex", "gap": "20px", "marginBottom": "20px"}, children=[
            html.Div(style={**card_style, "flex": "1"}, children=[
                dcc.Graph(id="bug-severity-bar"),
                dcc.Graph(id="uat-results-bar"),
            ]),
            html.Div(style={**card_style, "flex": "2", "display": "flex", "flexDirection": "column", "gap": "20px"}, children=[
                dcc.Graph(id="success-failure-bar"),
                dcc.Graph(id="response-time-bar"),
            ]),
        ]),

        # ─ Cluster B: Long-Term Statistics ─
        html.Div(style={"display": "flex", "gap": "20px"}, children=[
            # Error-Prone Functionality
            html.Div(style={**card_style, "flex": "1"}, children=[
                dcc.Graph(id="error-treemap")
            ]),
            # Test Case Pass Rate Over Sprints
            html.Div(style={**card_style, "flex": "1"}, children=[
                dcc.Graph(
                    figure=px.line(
                        summary_df,
                        x="Sprint",
                        y="% TCs Passed",
                        title="Test Case Pass Rate Over Sprints"
                    )
                )
            ]),
        ]),
    ]
)

@app.callback(
    Output("pass-rate", "children"),
    Output("bug-count", "children"),
    Output("loc-count", "children"),
    Output("bug-severity-bar", "figure"),
    Output("uat-results-bar", "figure"),
    Output("success-failure-bar", "figure"),
    Output("response-time-bar", "figure"),
    Output("error-treemap", "figure"),
    Input("sprint-selector", "value"),
)
def update_all(sprint_sel):
    # Key stats
    row = summary_df[summary_df["Sprint"] == sprint_sel].iloc[0]
    pr = f"{round(row['% TCs Passed'],2)}%"
    bc = f"{int(row['Total Bugs'])}"
    lc = f"{int(row['Total LOC'])}"

    # Bug severity bar
    sev = bugs_df.groupby("Priority").size().reset_index(name="Count")
    fig_sev = px.bar(
        sev, x="Priority", y="Count", color="Priority",
        color_discrete_map={"Low":"green","Medium":"orange","Critical":"red"},
        title="Open Bugs by Severity"
    )

    # UAT results bar
    uat_df = uat_all[uat_all["sprint"] == sprint_sel]
    counts = uat_df["Result"].value_counts()
    fig_uat = px.bar(
        x=["Pass","Fail"],
        y=[counts.get("Pass",0), counts.get("Fail",0)],
        color=["Pass","Fail"],
        color_discrete_map={"Pass":"green","Fail":"red"},
        title="UAT Test Results",
        labels={"x":"test_result","y":"no_of_tests"}
    )

    # Performance charts (stacked %)
    stats = compute_stats(df_all[df_all["sprint"] == sprint_sel])
    stats["total"] = stats["success_count"] + stats["failure_count"]
    stats["Success %"] = stats["success_count"] / stats["total"] * 100
    stats["Failure %"] = stats["failure_count"] / stats["total"] * 100
    fig_sf = px.bar(
        stats, x="label", y=["Success %","Failure %"],
        barmode="stack",
        color_discrete_map={"Success %":"#28a745","Failure %":"#dc3545"},
        title="Success vs Failure % by Endpoint"
    )

    fig_rt = px.bar(
        stats, x="label", y="avg_response_time_ms",
        color="avg_response_time_ms", color_continuous_scale="RdYlGn_r",
        title="Average Response Time (ms)"
    )

    # Error-Prone treemap
    all_s = pd.concat(sprint_summaries.values(), ignore_index=True)
    agg = all_s.groupby(["Module","User Story"])["Number of bugs"].sum().reset_index()
    fig_err = px.treemap(
        agg, path=["Module","User Story"], values="Number of bugs",
        color="Number of bugs", title="Error-Prone Functionality"
    )

    return pr, bc, lc, fig_sev, fig_uat, fig_sf, fig_rt, fig_err

if __name__ == "__main__":
    app.run(debug=True)