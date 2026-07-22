const movements = [
  {
    signal: 'Pricing',
    title: 'Enterprise packaging changed',
    time: '12 min ago',
    priority: 'High',
  },
  {
    signal: 'Hiring',
    title: 'New AI engineering roles',
    time: '3 hr ago',
    priority: 'Watch',
  },
  {
    signal: 'News',
    title: 'Partnership announcement',
    time: 'Yesterday',
    priority: 'New',
  },
]

export function IntelligencePreview() {
  return (
    <figure className="intelligence-preview">
      <figcaption>
        <div>
          <span className="preview-brand-dot" />
          <strong>Market overview</strong>
        </div>
        <span className="preview-status">
          Monitoring active
        </span>
      </figcaption>

      <div className="preview-summary-grid">
        <div>
          <span>Competitors monitored</span>
          <strong>03</strong>
        </div>
        <div>
          <span>Signals this week</span>
          <strong>08</strong>
        </div>
        <div>
          <span>Requires attention</span>
          <strong>02</strong>
        </div>
      </div>

      <section className="movement-chart">
        <header>
          <div>
            <span>
              Competitive movement
            </span>
            <strong>
              Activity is increasing
            </strong>
          </div>
          <span>LAST 30 DAYS</span>
        </header>

        <svg
          viewBox="0 0 600 180"
          role="img"
          aria-label="Sample competitive activity increasing over thirty days"
        >
          <path
            className="chart-grid-line"
            d="M0 35H600 M0 90H600 M0 145H600"
          />
          <path
            className="chart-area"
            d="M0 145 C65 138 85 118 135 124 C190 131 207 93 260 101 C310 109 336 72 390 81 C450 91 480 42 530 50 C560 54 580 29 600 20 L600 180 L0 180 Z"
          />
          <path
            className="chart-line"
            d="M0 145 C65 138 85 118 135 124 C190 131 207 93 260 101 C310 109 336 72 390 81 C450 91 480 42 530 50 C560 54 580 29 600 20"
          />
          <circle
            className="chart-point"
            cx="600"
            cy="20"
            r="6"
          />
        </svg>
      </section>

      <section className="movement-list">
        <header>
          <span>Latest movements</span>
          <span>View all</span>
        </header>

        {movements.map((movement) => (
          <article key={movement.title}>
            <div className="movement-icon">
              {movement.signal.charAt(0)}
            </div>
            <div>
              <span>{movement.signal}</span>
              <strong>{movement.title}</strong>
            </div>
            <div className="movement-time">
              <span>{movement.priority}</span>
              <time>{movement.time}</time>
            </div>
          </article>
        ))}
      </section>

      <footer>
        <span>
          SAMPLE PRODUCT VIEW
        </span>
        <span>
          Evidence linked to every insight
        </span>
      </footer>
    </figure>
  )
}
