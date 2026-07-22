import { Link } from 'react-router-dom'

import { BrandMark } from '../components/BrandMark'
import {
  ChangeToBriefPreview,
} from '../components/ChangeToBriefPreview'
import { useAuth } from '../hooks/useAuth'

const signals = [
  {
    name: 'Website',
    label: 'Positioning',
    description:
      'See positioning, messaging, and product changes as they happen.',
  },
  {
    name: 'Pricing',
    label: 'Packaging',
    description:
      'Track plans, packaging, prices, and feature movement.',
  },
  {
    name: 'Reviews',
    label: 'Sentiment',
    description:
      'Understand customer sentiment and emerging complaints.',
  },
  {
    name: 'Hiring',
    label: 'Direction',
    description:
      'Read strategic direction through teams, roles, and locations.',
  },
  {
    name: 'News',
    label: 'Narrative',
    description:
      'Follow announcements, partnerships, and market narratives.',
  },
]

const plans = [
  {
    name: 'Starter',
    price: '$49',
    description: 'For focused founders tracking a tight market.',
    features: [
      '3 monitored competitors',
      'Weekly intelligence brief',
      'Evidence-linked change history',
    ],
  },
  {
    name: 'Growth',
    price: '$149',
    description: 'For teams turning market movement into action.',
    featured: true,
    features: [
      '10 monitored competitors',
      'All five intelligence signals',
      'Priority briefs and team workspace',
    ],
  },
  {
    name: 'Scale',
    price: '$399',
    description: 'For established intelligence programs.',
    features: [
      '30 monitored competitors',
      'Executive reporting cadence',
      'Priority onboarding and support',
    ],
  },
]

const workflow = [
  {
    number: '01',
    title: 'Outpace watches',
    copy:
      'Your selected competitor sources are monitored on a recurring schedule.',
  },
  {
    number: '02',
    title: 'Change becomes context',
    copy:
      'Meaningful movement is separated from routine page noise.',
  },
  {
    number: '03',
    title: 'Your team decides',
    copy:
      'Each brief explains the evidence, significance, and next action.',
  },
]

export function LandingPage() {
  const { session } = useAuth()

  return (
    <div className="lux-page">
      <header className="lux-nav">
        <BrandMark />

        <nav aria-label="Main navigation">
          <a href="#platform">
            Platform
          </a>
          <a href="#signals">
            Signals
          </a>
          <a href="#workflow">
            How it works
          </a>
          <a href="#pricing">
            Pricing
          </a>
        </nav>

        <div className="lux-nav__actions">
          <Link
            className="lux-sign-in"
            to={
              session
                ? '/dashboard'
                : '/login'
            }
          >
            {session
              ? 'Open dashboard'
              : 'Sign in'}
          </Link>

          <Link
            className="lux-button lux-button--primary"
            to={
              session
                ? '/onboarding'
                : '/login'
            }
          >
            Start monitoring
          </Link>
        </div>
      </header>

      <main>
        <section
          className="lux-hero"
          id="platform"
        >
          <div className="lux-hero__copy">
            <p className="lux-kicker">
              Competitive intelligence,
              made clear
            </p>

            <h1>
              Know what changed.
              <span>
                Decide what comes next.
              </span>
            </h1>

            <p className="lux-hero__summary">
              Outpace brings competitor
              websites, pricing, reviews,
              hiring, and news into one calm
              intelligence stream—so your team
              can move with confidence.
            </p>

            <div className="lux-hero__actions">
              <Link
                className="lux-button lux-button--primary"
                to="/login"
              >
                Monitor your market
              </Link>

              <a
                className="lux-button lux-button--quiet"
                href="#signals"
              >
                Explore the platform
              </a>
            </div>

            <div className="lux-proof-points">
              <span>
                Evidence-backed
              </span>
              <span>
                Continuously monitored
              </span>
              <span>
                Decision-ready
              </span>
            </div>
          </div>

          <div className="lux-hero__visual">
            <div className="preview-aura" />
            <ChangeToBriefPreview />
          </div>
        </section>

        <section className="lux-trust-strip">
          <p>
            One view of the market around you
          </p>
          <div>
            <span>
              <strong>5</strong>
              intelligence channels
            </span>
            <span>
              <strong>1</strong>
              evidence-linked stream
            </span>
            <span>
              <strong>Always</strong>
              ready for review
            </span>
          </div>
        </section>

        <section
          className="lux-signals"
          id="signals"
        >
          <header className="lux-section-heading">
            <div>
              <p className="lux-kicker">
                A wider field of view
              </p>
              <h2>
                Your competitors leave signals
                everywhere.
              </h2>
            </div>

            <p>
              Outpace gathers the movements
              that matter and gives your team
              one place to understand them.
            </p>
          </header>

          <div className="lux-signal-grid">
            {signals.map((signal) => (
              <article key={signal.name}>
                <span className="signal-label">
                  {signal.label}
                </span>
                <h3>{signal.name}</h3>
                <p>{signal.description}</p>
                <span className="signal-rule" />
              </article>
            ))}
          </div>
        </section>

        <section
          className="lux-workflow"
          id="workflow"
        >
          <div className="lux-workflow__intro">
            <p className="lux-kicker">
              From movement to meaning
            </p>
            <h2>
              Less noise.
              <span>
                Better decisions.
              </span>
            </h2>
            <p>
              Monitoring runs quietly in the
              background. Your team sees the
              changes worth discussing.
            </p>
          </div>

          <div className="lux-workflow__steps">
            {workflow.map((step) => (
              <article key={step.number}>
                <span>{step.number}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.copy}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="lux-brief-showcase">
          <div className="lux-brief-showcase__copy">
            <p className="lux-kicker">
              Intelligence with a point of view
            </p>
            <h2>
              Every change comes with the
              answer to “so what?”
            </h2>
            <p>
              Outpace combines structured
              evidence with clear context and
              an actionable recommendation.
            </p>

            <ul>
              <li>
                Original evidence retained
              </li>
              <li>
                Significance explained
              </li>
              <li>
                Recommended response included
              </li>
            </ul>
          </div>

          <article className="executive-brief">
            <header>
              <div>
                <span>Sample intelligence brief</span>
                <strong>
                  Demo Analytics Company
                </strong>
              </div>
              <span className="brief-priority">
                High priority
              </span>
            </header>

            <div className="executive-brief__body">
              <span>
                Pricing and packaging
              </span>
              <h3>
                A new enterprise tier suggests
                a deliberate move upmarket.
              </h3>
              <p>
                Packaging changes point toward
                larger teams and a more
                sales-led buying motion.
              </p>

              <div>
                <section>
                  <span>
                    Why it matters
                  </span>
                  <p>
                    The competitor may be
                    preparing to pursue larger
                    accounts with more complex
                    requirements.
                  </p>
                </section>
                <section>
                  <span>
                    Recommended action
                  </span>
                  <p>
                    Review enterprise
                    differentiation and update
                    account-level talk tracks.
                  </p>
                </section>
              </div>
            </div>

            <footer>
              <span>
                SAMPLE / NOT A VERIFIED EVENT
              </span>
              <span>
                91% confidence
              </span>
            </footer>
          </article>
        </section>

        <section
          className="lux-pricing"
          id="pricing"
        >
          <header className="lux-pricing__heading">
            <div>
              <p className="lux-kicker">
                Clear plans, no noise
              </p>
              <h2>
                Start focused.
                <span>Expand your field of view.</span>
              </h2>
            </div>
            <p>
              Choose the monitoring depth that
              matches your market. Every plan
              keeps the evidence behind each
              insight.
            </p>
          </header>

          <div className="lux-pricing__grid">
            {plans.map((plan) => (
              <article
                className={
                  plan.featured
                    ? 'is-featured'
                    : undefined
                }
                key={plan.name}
              >
                <header>
                  <span>{plan.name}</span>
                  {plan.featured && (
                    <strong>Most popular</strong>
                  )}
                </header>
                <div className="plan-price">
                  <strong>{plan.price}</strong>
                  <span>/ month</span>
                </div>
                <p>{plan.description}</p>
                <ul>
                  {plan.features.map((feature) => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>
                <Link
                  className="lux-button lux-button--quiet"
                  to="/login"
                >
                  Start with {plan.name}
                </Link>
              </article>
            ))}
          </div>
        </section>

        <section className="lux-closing">
          <div>
            <p className="lux-kicker">
              Stay ahead of the conversation
            </p>
            <h2>
              Your market is already moving.
              <span>
                See it sooner.
              </span>
            </h2>
          </div>

          <Link
            className="lux-button lux-button--light"
            to="/login"
          >
            Start with one competitor
          </Link>
        </section>
      </main>

      <footer className="lux-footer">
        <BrandMark compact />
        <p>
          Evidence-led competitive intelligence.
        </p>
        <span>© 2026 Outpace</span>
      </footer>
    </div>
  )
}
