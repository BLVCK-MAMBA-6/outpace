const logLines = [
  '[08:42:30] snapshot collected',
  '[08:42:31] previous snapshot located',
  '[08:42:31] structured diff complete',
  '[08:42:32] 1 meaningful change detected',
  '[08:42:34] intelligence brief stored',
]

export function ProofConsole() {
  return (
    <figure className="proof-console">
      <figcaption className="console-bar">
        <span>
          SAMPLE MONITORING OUTPUT
        </span>
        <span className="console-live">
          <i aria-hidden="true" />
          LIVE SYSTEM
        </span>
      </figcaption>

      <div className="console-command">
        <span>$</span>{' '}
        outpace monitor rows
        {' '}
        --signal pricing
      </div>

      <div className="console-logs">
        {logLines.map((line) => (
          <div key={line}>
            {line}
          </div>
        ))}
      </div>

      <pre className="console-json">
{`{
  "signal": "pricing",
  "competitor": "Rows",
  "change": "enterprise_plan_added",
  "priority": "high",
  "confidence": 0.91
}`}
      </pre>

      <div className="console-result">
        <span>
          EVIDENCE / 04
        </span>
        <strong>
          Packaging movement detected
        </strong>
        <i
          className="terminal-cursor"
          aria-hidden="true"
        />
      </div>
    </figure>
  )
}
