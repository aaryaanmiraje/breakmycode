import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = "https://breakmycode-api.onrender.com";

const DEFAULT_CODE = ""

const ANALYSIS_MESSAGES = [
    "Initializing analysis...",
    "Scanning the obvious stuff...",
    "Hunting for edge cases...",
    "Pushing integer boundaries...",
    "Testing your assumptions...",
    "Looking for undefined behaviour...",
    "Trying inputs your professor forgot...",
    "Breaking things professionally...",
    "Compiling the evidence...",
];

const DEFAULT_SETTINGS = {
    animations: true,
    saveHistory: true,
};

function App() {
    const [code, setCode] = useState(DEFAULT_CODE);
    const [referenceCode, setReferenceCode] = useState("");
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [page, setPage] = useState("analyzer");
    const [analysisMessage, setAnalysisMessage] = useState(
        "Ready to break your code."
    );

    const [settings, setSettings] = useState(() => {
        try {
            return {
                ...DEFAULT_SETTINGS,
                ...JSON.parse(
                    localStorage.getItem("breakmycode_settings") || "{}"
                ),
            };
        } catch {
            return DEFAULT_SETTINGS;
        }
    });

    const [history, setHistory] = useState(() => {
        try {
            return JSON.parse(
                localStorage.getItem("breakmycode_history") || "[]"
            );
        } catch {
            return [];
        }
    });

    useEffect(() => {
        localStorage.setItem(
            "breakmycode_settings",
            JSON.stringify(settings)
        );
        document.body.classList.toggle(
            "reduced-motion",
            !settings.animations
        );
    }, [settings]);

    useEffect(() => {
        if (!loading) return;

        let index = 0;
        const timer = setInterval(() => {
            index = (index + 1) % ANALYSIS_MESSAGES.length;
            setAnalysisMessage(ANALYSIS_MESSAGES[index]);
        }, 700);

        return () => clearInterval(timer);
    }, [loading]);

    async function runAnalysis() {
        if (!code.trim()) {
            setError("There is no code to analyze.");
            return;
        }

        setLoading(true);
        setError("");
        setResult(null);
        setAnalysisMessage(ANALYSIS_MESSAGES[0]);

        try {
            const response = await fetch(`${API_URL}/analyze`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    code,
                    reference_code:
                        referenceCode.trim() === ""
                            ? null
                            : referenceCode,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof data?.detail === "string"
                        ? data.detail
                        : "Backend returned an error."
                );
            }

            setResult(data);
            setAnalysisMessage("Analysis complete.");

            if (settings.saveHistory) {
                const historyItem = {
                    id: Date.now(),
                    createdAt: new Date().toISOString(),
                    code,
                    referenceCode,
                    result: data,
                };

                setHistory((previous) => {
                    const updated = [historyItem, ...previous].slice(0, 20);
                    localStorage.setItem(
                        "breakmycode_history",
                        JSON.stringify(updated)
                    );
                    return updated;
                });
            }
        } catch (err) {
            setError(
                err.message || "Could not connect to BreakMyCode."
            );
        } finally {
            setLoading(false);
        }
    }

    function openHistoryItem(item) {
        setCode(item.code || DEFAULT_CODE);
        setReferenceCode(item.referenceCode || "");
        setResult(item.result || null);
        setError("");
        setPage("analyzer");
    }

    function clearHistory() {
        localStorage.removeItem("breakmycode_history");
        setHistory([]);
    }

    function toggleSetting(key) {
        setSettings((previous) => ({
            ...previous,
            [key]: !previous[key],
        }));
    }

    function resetSettings() {
        setSettings(DEFAULT_SETTINGS);
    }

    function resetAnalyzer() {
        setCode(DEFAULT_CODE);
        setReferenceCode("");
        setResult(null);
        setError("");
        setAnalysisMessage("Ready to break your code.");
        setPage("analyzer");
    }

    return (
        <div className="app">
            <aside className="sidebar">
                <div className="logo">
                    <span>&gt;_</span>
                    breakmycode
                </div>

                <div className="sidebar-section">
                    <div className="sidebar-label">WORKSPACE</div>

                    <NavButton
                        active={page === "analyzer"}
                        onClick={() => setPage("analyzer")}
                        icon="□"
                    >
                        Analyzer
                    </NavButton>

                    <NavButton
                        active={page === "history"}
                        onClick={() => setPage("history")}
                        icon="◌"
                    >
                        History
                    </NavButton>
                </div>

                <div className="sidebar-section">
                    <div className="sidebar-label">TOOLS</div>

                    <NavButton
                        active={page === "settings"}
                        onClick={() => setPage("settings")}
                        icon="⚙"
                    >
                        Settings
                    </NavButton>

                    <NavButton
                        active={page === "docs"}
                        onClick={() => setPage("docs")}
                        icon="?"
                    >
                        Documentation
                    </NavButton>
                </div>

                <div className="sidebar-bottom">
                    <div className="api-status">
                        <span className="online-dot"></span>
                        API connected
                    </div>

                    <div className="version">v1.0.0</div>
                </div>
            </aside>

            <main className="main">
                <header className="header">
                    <div>
                        <div className="breadcrumb">
                            workspace / {page}
                        </div>
                        <h1>
                            {page === "analyzer"
                                ? "Analyzer"
                                : page === "history"
                                    ? "History"
                                    : page === "settings"
                                        ? "Settings"
                                        : "Documentation"}
                        </h1>
                    </div>

                    <div className="header-right">
                        <div className="backend-status">
                            <span className="online-dot"></span>
                            localhost:8000
                        </div>

                        <button
                            className="header-button"
                            onClick={() => setPage("docs")}
                        >
                            Docs
                        </button>
                    </div>
                </header>

                {page === "analyzer" && (
                    <Analyzer
                        code={code}
                        setCode={setCode}
                        referenceCode={referenceCode}
                        setReferenceCode={setReferenceCode}
                        result={result}
                        loading={loading}
                        error={error}
                        analysisMessage={analysisMessage}
                        runAnalysis={runAnalysis}
                        onReset={resetAnalyzer}
                    />
                )}

                {page === "history" && (
                    <HistoryPage
                        history={history}
                        onSelect={openHistoryItem}
                        onClear={clearHistory}
                    />
                )}

                {page === "settings" && (
                    <SettingsPage
                        settings={settings}
                        toggleSetting={toggleSetting}
                        resetSettings={resetSettings}
                        clearHistory={clearHistory}
                        historyCount={history.length}
                    />
                )}

                {page === "docs" && <DocumentationPage />}
            </main>
        </div>
    );
}

function NavButton({ active, onClick, icon, children }) {
    return (
        <button
            className={`nav-item ${active ? "active" : ""}`}
            onClick={onClick}
        >
            <span>{icon}</span>
            {children}
        </button>
    );
}

function Analyzer({
    code,
    setCode,
    referenceCode,
    setReferenceCode,
    result,
    loading,
    error,
    analysisMessage,
    runAnalysis,
    onReset,
}) {
    const summary = result?.summary || {};
    const weaknesses = result?.weaknesses || [];
    const aiFindings = result?.ai_review?.findings || [];

    const tests = result?.tests_executed || 0;
    const passed = summary.passed || 0;
    const issues = weaknesses.length;
    const overflows = summary.integer_overflows || 0;
    const wrongAnswers = summary.wrong_answers || 0;

    const hasHighRisk = weaknesses.some(
        (issue) => getSeverity(issue) === "HIGH"
    );

    const aiHasHighRisk = aiFindings.some(
        (finding) =>
            String(
                finding.severity || finding.confidence || ""
            ).toUpperCase() === "HIGH"
    );

    const risk =
        issues === 0
            ? "LOW"
            : hasHighRisk || aiHasHighRisk
                ? "HIGH"
                : "MEDIUM";

    const riskPercent =
        risk === "HIGH" ? 90 : risk === "MEDIUM" ? 55 : 20;

    return (
        <>
            <div className="workspace">
                <section className="editor-area">
                    <div className="section-heading">
                        <div>
                            <div className="eyebrow">SOURCE ANALYSIS</div>
                            <h2>Your code</h2>
                            <p>Give us something to break.</p>
                        </div>

                        <div className="heading-actions">
                            <div className="file-name">main.cpp</div>
                            <button
                                className="mini-button"
                                onClick={onReset}
                            >
                                RESET
                            </button>
                        </div>
                    </div>

                    <div className="editor-card">
                        <div className="editor-toolbar">
                            <div className="window-controls">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>

                            <div className="editor-toolbar-right">
                                <span className="editor-language">
                                    C++17
                                </span>
                                <span className="editor-live">
                                    EDITABLE
                                </span>
                            </div>
                        </div>

                        <div className="editor">
                            <div className="line-numbers">
                                {code.split("\n").map((_, index) => (
                                    <div key={index}>{index + 1}</div>
                                ))}
                            </div>

                            <textarea
                                value={code}
                                onChange={(event) =>
                                    setCode(event.target.value)
                                }
                                spellCheck="false"
                                  placeholder={`Paste your code here...
Give us something to break.`}
/>
                            
                        </div>
                    </div>

                    <div className="reference-card">
                        <div className="reference-header">
                            <div>
                                <strong>
                                    Known-good implementation
                                </strong>
                                <span>OPTIONAL</span>
                            </div>
                            <span className="reference-help">
                                Compare behavior when supplied
                            </span>
                        </div>

                        <textarea
                            className="reference-editor"
                            value={referenceCode}
                            onChange={(event) =>
                                setReferenceCode(event.target.value)
                            }
                            placeholder="Optional: paste the correct implementation here..."
                            spellCheck="false"
                        />
                    </div>

                    <div className="run-row">
                        <button
                            className="run-button"
                            onClick={runAnalysis}
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <span className="spinner"></span>
                                    ANALYZING
                                </>
                            ) : (
                                <>
                                    <span>⚡</span>
                                    BREAK MY CODE
                                </>
                            )}
                        </button>

                        <div className="run-info">
                            {loading
                                ? analysisMessage
                                : "Ready to analyze"}
                        </div>
                    </div>

                    {error && (
                        <div className="error-message">
                            <strong>Analysis failed</strong>
                            <span>{error}</span>
                        </div>
                    )}
                </section>

                <section className="results-panel">
                    <div className="results-top">
                        <div>
                            <div className="small-label">
                                LATEST ANALYSIS
                            </div>
                            <h2>Results</h2>
                        </div>

                        {result && (
                            <div
                                className={`result-status ${
                                    issues ? "danger" : "safe"
                                }`}
                            >
                                {issues
                                    ? "⚠ ISSUES FOUND"
                                    : "✓ SURVIVED"}
                            </div>
                        )}
                    </div>

                    {!result && !loading && (
                        <div className="empty-results">
                            <div className="empty-icon">⚡</div>
                            <div className="empty-kicker">
                                READY WHEN YOU ARE
                            </div>
                            <h3>
                                Your code is suspiciously quiet.
                            </h3>
                            <p>
                                Hit the button and we'll throw nasty
                                inputs at it.
                            </p>
                            <div className="empty-hint">
                                Static checks + generated tests +
                                differential behaviour
                            </div>
                        </div>
                    )}

                    {loading && (
                        <div className="analysis-screen">
                            <div className="analysis-symbol">⚡</div>
                            <div className="analysis-title">
                                BREAKING CODE
                            </div>
                            <div className="analysis-message">
                                {analysisMessage}
                            </div>
                            <div className="analysis-bars">
                                {Array.from({ length: 6 }).map(
                                    (_, index) => (
                                        <span key={index}></span>
                                    )
                                )}
                            </div>
                        </div>
                    )}

                    {result && !loading && (
                        <>
                            <div className="stats-grid">
                                <Stat
                                    label="TESTS"
                                    value={tests}
                                    caption="attempted"
                                />
                                <Stat
                                    label="SURVIVED"
                                    value={passed}
                                    caption="tests"
                                    tone="safe"
                                />
                                <Stat
                                    label="VULNERABILITIES"
                                    value={issues}
                                    caption="found"
                                    tone="danger"
                                />
                                <Stat
                                    label="OVERFLOWS"
                                    value={overflows}
                                    caption="detected"
                                />
                            </div>

                            <div className="risk-card">
                                <div className="risk-header">
                                    <span>RISK LEVEL</span>
                                    <strong
                                        className={`risk-${risk.toLowerCase()}`}
                                    >
                                        {risk}
                                    </strong>
                                </div>

                                <div className="risk-track">
                                    <div
                                        className={`risk-fill risk-${risk.toLowerCase()}`}
                                        style={{
                                            width: `${riskPercent}%`,
                                        }}
                                    />
                                </div>

                                <div className="risk-caption">
                                    {risk === "HIGH" &&
                                        "High-risk behaviour detected. This code needs attention."}
                                    {risk === "MEDIUM" &&
                                        "Some weaknesses were detected. Worth investigating."}
                                    {risk === "LOW" &&
                                        "Nothing suspicious was detected. Nice work."}
                                </div>
                            </div>

                            <div className="result-section">
                                <div className="result-section-title">
                                    <span>⚠ FINDINGS</span>
                                    <span>{issues}</span>
                                </div>

                                {weaknesses.length > 0 ? (
                                    <div className="issues">
                                        {weaknesses.map((issue, index) => (
                                            <IssueCard
                                                issue={issue}
                                                key={index}
                                            />
                                        ))}
                                    </div>
                                ) : (
                                    <div className="survived-card">
                                        <div className="survived-icon">
                                            ✓
                                        </div>
                                        <div>
                                            <strong>
                                                No failing behaviour found
                                            </strong>
                                            <p>
                                                The generated tests did not
                                                expose a vulnerability.
                                            </p>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {aiFindings.length > 0 && (
                                <div className="breakbot">
                                    <div className="breakbot-header">
                                        <div className="ai-mark">AI</div>
                                        <div>
                                            <strong>BreakBot Review</strong>
                                            <small>
                                                Additional reasoning about
                                                the findings
                                            </small>
                                        </div>
                                    </div>

                                    {aiFindings.map((finding, index) => (
                                        <div
                                            className="ai-finding"
                                            key={index}
                                        >
                                            <strong>
                                                {finding.title ||
                                                    finding.type ||
                                                    "Finding"}
                                            </strong>

                                            {finding.explanation && (
                                                <p>
                                                    {finding.explanation}
                                                </p>
                                            )}

                                            {finding.fix && (
                                                <p>
                                                    <b>Fix:</b>{" "}
                                                    {finding.fix}
                                                </p>
                                            )}

                                            {finding.suggested_code && (
                                                <pre>
                                                    {
                                                        finding.suggested_code
                                                    }
                                                </pre>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </>
                    )}
                </section>
            </div>

            {result && (
                <div className="summary-bar">
                    <SummaryMetric label="TESTS" value={tests} />
                    <SummaryMetric
                        label="SURVIVED"
                        value={passed}
                    />
                    <SummaryMetric
                        label="OVERFLOWS"
                        value={overflows}
                    />
                    <SummaryMetric
                        label="WRONG ANSWERS"
                        value={wrongAnswers}
                    />

                    <div className="footer-message">
                        {issues
                            ? "Your code has some explaining to do."
                            : "Nothing broke. Suspicious."}
                    </div>
                </div>
            )}
        </>
    );
}

function Stat({ label, value, caption, tone = "" }) {
    return (
        <div className={`stat ${tone}`}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{caption}</small>
        </div>
    );
}

function SummaryMetric({ label, value }) {
    return (
        <div>
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
}

function IssueCard({ issue }) {
    const severity = getSeverity(issue);

    return (
        <div className="issue">
            <div className="issue-indicator"></div>

            <div className="issue-body">
                <div className="issue-heading">
                    <strong>{formatTitle(issue.type)}</strong>
                    <span
                        className={`severity ${severity.toLowerCase()}`}
                    >
                        {severity}
                    </span>
                </div>

                {issue.input !== undefined &&
                    issue.input !== null && (
                        <div className="issue-input">
                            <span>BREAKING INPUT</span>
                            <code>{String(issue.input)}</code>
                        </div>
                    )}

                <p>
                    {issue.reason ||
                        "The analyzer found unexpected behaviour."}
                </p>

                {issue.fix && (
                    <div className="issue-fix">
                        <span>HOW TO FIX</span>
                        <p>{issue.fix}</p>
                    </div>
                )}

                {issue.suggested_code && (
                    <pre>{issue.suggested_code}</pre>
                )}
            </div>
        </div>
    );
}

function HistoryPage({ history, onSelect, onClear }) {
    const totals = useMemo(() => {
        const vulnerabilities = history.reduce(
            (sum, item) =>
                sum + (item.result?.weaknesses?.length || 0),
            0
        );

        const tests = history.reduce(
            (sum, item) =>
                sum + (item.result?.tests_executed || 0),
            0
        );

        return { vulnerabilities, tests };
    }, [history]);

    return (
        <section className="page-content history-page">
            <div className="page-hero">
                <div>
                    <div className="small-label">PAST ANALYSES</div>
                    <h2>History</h2>
                    <p>
                        Every previous BreakMyCode run, kept locally on
                        this device.
                    </p>
                </div>

                {history.length > 0 && (
                    <button
                        className="clear-history"
                        onClick={onClear}
                    >
                        Clear history
                    </button>
                )}
            </div>

            {history.length > 0 && (
                <div className="history-overview">
                    <div>
                        <span>RUNS</span>
                        <strong>{history.length}</strong>
                    </div>
                    <div>
                        <span>TESTS EXECUTED</span>
                        <strong>{totals.tests}</strong>
                    </div>
                    <div>
                        <span>ISSUES FOUND</span>
                        <strong>{totals.vulnerabilities}</strong>
                    </div>
                </div>
            )}

            {history.length === 0 ? (
                <div className="history-empty">
                    <div className="history-empty-icon">◌</div>
                    <div className="empty-kicker">NOTHING HERE YET</div>
                    <h3>No analyses yet.</h3>
                    <p>
                        Run your first analysis and it will appear here.
                    </p>
                </div>
            ) : (
                <div className="history-list">
                    {history.map((item) => {
                        const summary = item.result?.summary || {};
                        const weaknesses =
                            item.result?.weaknesses || [];

                        const hasHighRisk = weaknesses.some(
                            (issue) =>
                                getSeverity(issue) === "HIGH"
                        );

                        const risk =
                            weaknesses.length === 0
                                ? "LOW"
                                : hasHighRisk
                                    ? "HIGH"
                                    : "MEDIUM";

                        const tests =
                            item.result?.tests_executed || 0;
                        const passed = summary.passed || 0;

                        return (
                            <div
                                className="history-item"
                                key={item.id}
                            >
                                <div
                                    className={`history-risk ${risk.toLowerCase()}`}
                                >
                                    {risk}
                                </div>

                                <div className="history-info">
                                    <div className="history-title-row">
                                        <strong>
                                            {weaknesses.length > 0
                                                ? formatTitle(
                                                    weaknesses[0]?.type
                                                )
                                                : "Clean Run"}
                                        </strong>
                                        <span className="history-status">
                                            {weaknesses.length > 0
                                                ? "Issues found"
                                                : "Passed"}
                                        </span>
                                    </div>

                                    <div className="history-meta">
                                        <span>
                                            {tests} tests
                                        </span>
                                        <span>•</span>
                                        <span>
                                            {passed} survived
                                        </span>
                                        <span>•</span>
                                        <span>
                                            {formatHistoryDate(
                                                item.createdAt
                                            )}
                                        </span>
                                    </div>
                                </div>

                                <button
                                    className="view-history"
                                    onClick={() => onSelect(item)}
                                >
                                    VIEW
                                    <span>→</span>
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}
        </section>
    );
}

function SettingsPage({
    settings,
    toggleSetting,
    resetSettings,
    clearHistory,
    historyCount,
}) {
    return (
        <section className="page-content settings-page">
            <div className="page-hero">
                <div>
                    <div className="small-label">PREFERENCES</div>
                    <h2>Settings</h2>
                    <p>
                        Tune the workspace without changing how analysis
                        works.
                    </p>
                </div>
            </div>

            <div className="settings-grid">
                <div className="settings-card">
                    <div className="settings-card-heading">
                        <div className="small-label">INTERFACE</div>
                        <h3>Workspace preferences</h3>
                    </div>

                    <SettingRow
                        title="Animations"
                        description="Keep loading and result transitions enabled."
                        enabled={settings.animations}
                        onClick={() => toggleSetting("animations")}
                    />

                    <SettingRow
                        title="Save analysis history"
                        description="Keep your latest 20 runs in this browser's local storage."
                        enabled={settings.saveHistory}
                        onClick={() => toggleSetting("saveHistory")}
                    />
                </div>

                <div className="settings-card">
                    <div className="settings-card-heading">
                        <div className="small-label">DATA</div>
                        <h3>Local workspace data</h3>
                    </div>

                    <div className="settings-stats">
                        <div>
                            <strong>{historyCount}</strong>
                            <span>saved analyses</span>
                        </div>
                        <div>
                            <strong>20</strong>
                            <span>maximum stored runs</span>
                        </div>
                    </div>

                    <div className="settings-actions">
                        <button
                            className="outline-danger"
                            onClick={clearHistory}
                            disabled={historyCount === 0}
                        >
                            Clear saved history
                        </button>

                        <button
                            className="secondary-button"
                            onClick={resetSettings}
                        >
                            Reset preferences
                        </button>
                    </div>
                </div>
            </div>

            <div className="settings-note">
                <span>●</span>
                <div>
                    <strong>Privacy by default</strong>
                    <p>
                        History is stored in your browser's local storage.
                        It is not sent to the backend as a separate history
                        database.
                    </p>
                </div>
            </div>
        </section>
    );
}

function SettingRow({ title, description, enabled, onClick }) {
    return (
        <div className="setting-row">
            <div>
                <strong>{title}</strong>
                <p>{description}</p>
            </div>

            <button
                className={`toggle ${enabled ? "on" : ""}`}
                onClick={onClick}
                aria-label={`${title}: ${
                    enabled ? "on" : "off"
                }`}
                aria-pressed={enabled}
            >
                <span></span>
            </button>
        </div>
    );
}

function DocumentationPage() {
    return (
        <section className="page-content docs-page">
            <div className="page-hero">
                <div>
                    <div className="small-label">REFERENCE</div>
                    <h2>Documentation</h2>
                    <p>
                        A quick guide to getting useful results from
                        BreakMyCode.
                    </p>
                </div>
            </div>

            <div className="docs-grid">
                <DocCard
                    number="01"
                    title="Paste your code"
                    text="Put the C++17 program you want to inspect into the main editor. BreakMyCode uses that source as the program under test."
                />

                <DocCard
                    number="02"
                    title="Add a reference"
                    text="If you have a known-good implementation, paste it into the optional reference editor. This gives the analyzer another way to identify behavioural differences."
                />

                <DocCard
                    number="03"
                    title="Run analysis"
                    text="BreakMyCode compiles the program, generates test inputs, executes them, and looks for crashes, timeouts, incorrect behaviour, and other weaknesses."
                />

                <DocCard
                    number="04"
                    title="Read the findings"
                    text="Use the risk level, failing input, explanation, suggested fix, and optional BreakBot review to understand what actually went wrong."
                />

                <DocCard
                    number="05"
                    title="Review history"
                    text="Successful analysis runs are saved locally when history is enabled. Open any previous run to restore its source and results."
                />

                <DocCard
                    number="06"
                    title="Keep improving"
                    text="Fix the reported weakness, run the analysis again, and compare the new result. The goal is not a score — it is code that survives hostile inputs."
                />
            </div>

            <div className="docs-callout">
                <div className="docs-callout-icon">⚡</div>
                <div>
                    <strong>What BreakMyCode is looking for</strong>
                    <p>
                        Integer overflow, wrong answers, crashes, timeouts,
                        undefined behaviour, and mismatches against a
                        supplied reference implementation.
                    </p>
                </div>
            </div>
        </section>
    );
}

function DocCard({ number, title, text }) {
    return (
        <article className="doc-card">
            <div className="doc-number">{number}</div>
            <h3>{title}</h3>
            <p>{text}</p>
        </article>
    );
}

function getSeverity(issue) {
    const level = String(
        issue?.severity || issue?.confidence || "MEDIUM"
    ).toUpperCase();

    if (["HIGH", "MEDIUM", "LOW"].includes(level)) {
        return level;
    }

    return "MEDIUM";
}

function formatTitle(type = "") {
    return String(type)
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatHistoryDate(date) {
    const time = new Date(date);

    if (Number.isNaN(time.getTime())) {
        return "Unknown date";
    }

    return time.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

export default App;