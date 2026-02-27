"""
Mock Reddit scraper — generates realistic developer-community posts
so the full Claude → DB → Report pipeline can be tested without
Reddit API credentials.

Swap out for the real RedditScraper once you have Reddit creds.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.reddit_scraper import RedditPost

_MOCK_POSTS_RAW = [
    # ── programming ────────────────────────────────────────────────────────
    {
        "subreddit": "programming",
        "title": "Bun 1.2 is incredibly fast — we replaced Node.js and cut CI time by 40%",
        "selftext": (
            "We migrated our monorepo from Node 20 to Bun 1.2 last sprint. "
            "Install times dropped from 45s to 8s, test runs are 3x faster, "
            "and the built-in SQLite bindings removed a whole dependency. "
            "The compatibility with existing npm packages is surprisingly good — "
            "we only hit two minor issues in 200k lines of TypeScript."
        ),
        "score": 3400,
        "num_comments": 412,
        "url": "https://reddit.com/r/programming/bun12",
        "comments": [
            "We did the same migration six months ago. Never looked back. The hot-reload speed alone is worth it.",
            "Bun's test runner is legitimately great. Jest config nightmares are gone.",
            "Still cautious about production use but for tooling and scripts it's a no-brainer.",
            "The bundler beats esbuild in our benchmarks by ~15%. Wild.",
        ],
    },
    {
        "subreddit": "programming",
        "title": "Rust async traits are finally stable — what this means for the ecosystem",
        "selftext": (
            "The stabilisation of async fn in traits in Rust 1.75 unblocks so many "
            "crates that have been waiting on workarounds like async-trait. Tower, "
            "axum, and several ORMs are already shipping updates."
        ),
        "score": 5100,
        "num_comments": 634,
        "url": "https://reddit.com/r/programming/rust-async-traits",
        "comments": [
            "Finally. I've been copy-pasting the async-trait macro boilerplate for two years.",
            "axum's new version with native async traits is noticeably cleaner. Great DX.",
            "Tokio + axum + async traits = my favourite backend stack right now.",
        ],
    },
    {
        "subreddit": "programming",
        "title": "Zed editor goes open source — and it's absurdly fast",
        "selftext": (
            "Zed, the editor built in Rust by the Atom creators, just open-sourced "
            "the full codebase. GPU rendering via GPUI, built-in AI pair programming, "
            "and collaborative editing."
        ),
        "score": 7200,
        "num_comments": 891,
        "url": "https://reddit.com/r/programming/zed-open-source",
        "comments": [
            "Switched from VS Code a month ago. The snappiness is real — especially on large files.",
            "The built-in terminal and git blame are solid.",
            "For Rust development specifically, the rust-analyzer integration is top-tier.",
            "Finally an editor that doesn't feel like a browser tab.",
        ],
    },
    # ── webdev ─────────────────────────────────────────────────────────────
    {
        "subreddit": "webdev",
        "title": "I rebuilt my SaaS with htmx and removed 90% of my JavaScript",
        "selftext": (
            "Spent 3 months converting a React SPA to htmx + Django. "
            "The codebase went from 45k lines to 18k. Page loads are faster "
            "because we're not shipping a JS bundle."
        ),
        "score": 4800,
        "num_comments": 723,
        "url": "https://reddit.com/r/webdev/htmx-rewrite",
        "comments": [
            "htmx changed how I think about web architecture. Hypermedia is underrated.",
            "The htmx + Django combo is great but I'd recommend Tailwind over raw CSS.",
            "Carson Gross deserves massive credit. htmx is a genuine paradigm shift.",
        ],
    },
    {
        "subreddit": "webdev",
        "title": "Astro 4.0 — the content layer is a game changer",
        "selftext": (
            "Astro's new content layer with type-safe collections and server islands "
            "makes it the most compelling choice for marketing sites, blogs, and docs."
        ),
        "score": 2900,
        "num_comments": 318,
        "url": "https://reddit.com/r/webdev/astro4",
        "comments": [
            "Migrated our docs site from Next.js to Astro. Build times went from 4min to 40s.",
            "Content collections with Zod schemas = never writing frontmatter validation again.",
            "Server islands is the right model.",
        ],
    },
    {
        "subreddit": "webdev",
        "title": "shadcn/ui hit 50k GitHub stars — why it won the component library wars",
        "selftext": (
            "shadcn/ui's model of copy-paste components you own turns out to be "
            "exactly what teams want. Full customisation, no fighting the library's opinions."
        ),
        "score": 6100,
        "num_comments": 544,
        "url": "https://reddit.com/r/webdev/shadcn-50k",
        "comments": [
            "The 'you own the code' model is genuinely superior for long-lived projects.",
            "Radix UI primitives underneath means accessibility is handled correctly.",
            "shadcn + Next.js + tRPC is my go-to stack for new SaaS projects.",
        ],
    },
    # ── devops ─────────────────────────────────────────────────────────────
    {
        "subreddit": "devops",
        "title": "We replaced Terraform with OpenTofu in production — here's how it went",
        "selftext": (
            "After HashiCorp's licence change we spent Q4 migrating 300+ Terraform "
            "modules to OpenTofu. State files are compatible and the CLI is a drop-in replacement."
        ),
        "score": 3700,
        "num_comments": 489,
        "url": "https://reddit.com/r/devops/opentofu-migration",
        "comments": [
            "Did the same. The OpenTofu community is moving fast.",
            "The CNCF backing makes this a safe long-term bet for enterprises.",
            "Provider compatibility has been flawless in our experience.",
        ],
    },
    {
        "subreddit": "devops",
        "title": "Coolify v4 is a genuinely great self-hosted Heroku/Vercel alternative",
        "selftext": (
            "Been running Coolify on a $12/mo Hetzner box for 6 months. "
            "Docker deployments, SSL certs, databases, cron jobs — all in a clean UI. "
            "I've moved 8 projects off Heroku and saving ~$400/mo."
        ),
        "score": 5500,
        "num_comments": 672,
        "url": "https://reddit.com/r/devops/coolify-v4",
        "comments": [
            "Coolify + Hetzner is the stack every indie hacker should know about.",
            "I evaluated Dokku, CapRover, and Coolify. Coolify wins on UX by a mile.",
            "The one-click database backups to S3 are a killer feature.",
        ],
    },
    {
        "subreddit": "devops",
        "title": "Cilium is replacing kube-proxy in most major cloud providers",
        "selftext": (
            "eBPF-based networking with Cilium provides better observability and "
            "significant performance improvements over iptables-based kube-proxy."
        ),
        "score": 2800,
        "num_comments": 231,
        "url": "https://reddit.com/r/devops/cilium-ebpf",
        "comments": [
            "Cilium + Hubble replaced our entire service mesh. Simpler and faster than Istio.",
            "eBPF is the most exciting infrastructure technology of the decade.",
        ],
    },
    # ── SideProject ────────────────────────────────────────────────────────
    {
        "subreddit": "SideProject",
        "title": "I built a SaaS with Supabase in a weekend and got 200 signups",
        "selftext": (
            "Used Supabase for auth, database, and storage. Row-level security "
            "policies handle multi-tenancy without extra code. From idea to deployed product in 48 hours."
        ),
        "score": 4200,
        "num_comments": 567,
        "url": "https://reddit.com/r/SideProject/supabase-weekend",
        "comments": [
            "Supabase is the reason solo founders can compete with funded startups now.",
            "The realtime subscriptions with RLS are killer for collaborative features.",
            "Auth + DB + Storage + Edge Functions in one platform is genuinely revolutionary.",
        ],
    },
    {
        "subreddit": "SideProject",
        "title": "Shipped my first product using Cursor AI — cut dev time in half",
        "selftext": (
            "Used Cursor's AI-assisted coding for a 3-month project. The Composer feature "
            "for multi-file edits saved me countless hours. Would estimate 40-50% productivity boost."
        ),
        "score": 3900,
        "num_comments": 445,
        "url": "https://reddit.com/r/SideProject/cursor-ai-review",
        "comments": [
            "Cursor is the first AI coding tool that actually changed my workflow.",
            "The codebase chat feature is where it really shines over GitHub Copilot.",
        ],
    },
    # ── indiehackers ───────────────────────────────────────────────────────
    {
        "subreddit": "indiehackers",
        "title": "PlanetScale's free tier killed my project — why Neon is the new default",
        "selftext": (
            "When PlanetScale removed their free tier I migrated 5 projects to Neon "
            "(serverless Postgres). Branching databases for preview environments is a killer feature."
        ),
        "score": 4600,
        "num_comments": 612,
        "url": "https://reddit.com/r/indiehackers/neon-postgres",
        "comments": [
            "Neon's database branching for Vercel preview deployments is magic.",
            "Scale to zero + generous free tier = perfect for side projects.",
            "I've moved 8 projects to Neon since the PlanetScale pricing change.",
        ],
    },
    {
        "subreddit": "indiehackers",
        "title": "How I use Resend + React Email to send beautiful transactional emails",
        "selftext": (
            "Resend is a developer-first email API with a React component library. "
            "Write emails in JSX, preview in the browser, send via a clean REST API."
        ),
        "score": 2700,
        "num_comments": 287,
        "url": "https://reddit.com/r/indiehackers/resend-react-email",
        "comments": [
            "React Email templates are genuinely a joy to write.",
            "Replaced SendGrid with Resend across all my projects. Never going back.",
        ],
    },
    # ── devtools ───────────────────────────────────────────────────────────
    {
        "subreddit": "devtools",
        "title": "Warp terminal is redefining what a terminal can be",
        "selftext": (
            "Warp is a Rust-based terminal with block-based output, AI command search, "
            "and collaborative features. The AI can explain error messages and generate commands."
        ),
        "score": 3800,
        "num_comments": 467,
        "url": "https://reddit.com/r/devtools/warp-terminal",
        "comments": [
            "The block model for command output makes scrolling through logs actually pleasant.",
            "AI command search saved me from man pages. I just describe what I want.",
            "It's on Linux now too — that was my blocker.",
        ],
    },
    {
        "subreddit": "devtools",
        "title": "Biome replaced ESLint + Prettier in our project — 10x faster linting",
        "selftext": (
            "Biome is a Rust-based formatter and linter that replaces both ESLint and Prettier. "
            "Single binary, zero config to start, CI lint step went from 45s to 4s."
        ),
        "score": 3100,
        "num_comments": 356,
        "url": "https://reddit.com/r/devtools/biome-eslint-replacement",
        "comments": [
            "Finally tried Biome this week. The speed is legitimately shocking.",
            "The migration from ESLint is mostly automatic with biome migrate.",
        ],
    },
]


def build_mock_posts() -> list[RedditPost]:
    """Convert raw mock data into RedditPost objects with realistic timestamps."""
    posts: list[RedditPost] = []
    base_time = datetime.now(tz=timezone.utc) - timedelta(days=3)

    for i, raw in enumerate(_MOCK_POSTS_RAW):
        post = RedditPost(
            post_id=f"mock_{i:04d}",
            title=raw["title"],
            selftext=raw.get("selftext", ""),
            url=raw["url"],
            score=raw["score"],
            num_comments=raw["num_comments"],
            subreddit=raw["subreddit"],
            created_utc=base_time - timedelta(hours=i * 4),
            top_comments=raw.get("comments", []),
            author=f"mock_user_{i}",
        )
        posts.append(post)

    return posts
