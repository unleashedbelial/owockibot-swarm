#!/usr/bin/env python3
"""
Owockibot Multi-Agent Swarm
Scout + Strategist agents coordinating on the real owockibot bounty board.
Runs continuously — analyzes ecosystem, monitors opportunities, tracks portfolio.
"""

import json
import urllib.request
import datetime
import hashlib
from collections import Counter, defaultdict

BOUNTY_BOARD_URL = "https://www.owockibot.xyz/api/bounty-board"
OUR_WALLET = "0x5ed8D2cf60cBe9c71Ab13A6b75f35BBC16F455cB".lower()

INFRA_KEYWORDS = ["dashboard", "api", "feed", "tracker", "monitor", "bot", "script",
                  "tool", "build", "deploy", "data", "chart", "visual"]
CONTENT_KEYWORDS = ["write", "thread", "tutorial", "blog", "post", "content", "explain",
                    "article", "guide"]
PROTOCOL_KEYWORDS = ["swarm", "multi-agent", "protocol", "coordination", "a2a", "agent",
                     "demo", "simulation"]
HARD_KEYWORDS = ["solidity", "smart contract audit", "zk proof", "3d model", "video production"]


def fetch_bounties():
    req = urllib.request.Request(
        BOUNTY_BOARD_URL,
        headers={"User-Agent": "owockibot-swarm-agent/1.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def categorize(title, desc):
    t = (title + " " + desc).lower()
    if any(k in t for k in PROTOCOL_KEYWORDS):
        return "Protocol/Agent"
    if any(k in t for k in INFRA_KEYWORDS):
        return "Infrastructure"
    if any(k in t for k in CONTENT_KEYWORDS):
        return "Content"
    return "Other"


def ts():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class ScoutAgent:
    id = "scout"
    name = "Scout"
    role = "Bounty Researcher"
    color = "#ff6b35"

    def scan_board(self, bounties):
        status_counts = Counter(b["status"] for b in bounties)
        open_unclaimed = [b for b in bounties if b["status"] == "open" and not b.get("claimer_address")]
        claimed_by_others = [b for b in bounties if b["status"] == "claimed"
                             and (b.get("claimer_address") or "").lower() != OUR_WALLET]
        return {
            "total": len(bounties),
            "by_status": dict(status_counts),
            "open_unclaimed": len(open_unclaimed),
            "claimed_by_others": len(claimed_by_others),
            "open_unclaimed_list": [
                {"id": b["id"], "title": b["title"], "reward": b["reward_usdc"]}
                for b in open_unclaimed[:5]
            ]
        }

    def analyze_competition(self, bounties):
        claimer_stats = defaultdict(lambda: {"count": 0, "usdc": 0, "completed": 0})
        for b in bounties:
            addr = (b.get("claimer_address") or "").lower()
            if addr and addr != OUR_WALLET:
                claimer_stats[addr]["count"] += 1
                claimer_stats[addr]["usdc"] += b["reward_usdc"]
                if b["status"] == "completed":
                    claimer_stats[addr]["completed"] += 1

        top_competitors = sorted(
            [{"addr": k[:10] + "...", "claims": v["count"], "completed": v["completed"], "usdc": v["usdc"]}
             for k, v in claimer_stats.items()],
            key=lambda x: x["completed"], reverse=True
        )[:4]

        return {"top_competitors": top_competitors, "total_competitors": len(claimer_stats)}

    def analyze_portfolio(self, bounties):
        ours = [b for b in bounties if (b.get("claimer_address") or "").lower() == OUR_WALLET]
        by_status = Counter(b["status"] for b in ours)
        submitted_usdc = sum(b["reward_usdc"] for b in ours if b["status"] == "submitted")
        completed_usdc = sum(b["reward_usdc"] for b in ours if b["status"] == "completed")
        active = [{"id": b["id"], "title": b["title"], "reward": b["reward_usdc"]}
                  for b in ours if b["status"] == "claimed"]
        submitted = [{"id": b["id"], "title": b["title"], "reward": b["reward_usdc"]}
                     for b in ours if b["status"] == "submitted"]
        return {
            "total_ours": len(ours),
            "by_status": dict(by_status),
            "submitted_pending_usdc": submitted_usdc,
            "completed_earned_usdc": completed_usdc,
            "active": active,
            "submitted": submitted
        }

    def analyze_categories(self, bounties):
        completed = [b for b in bounties if b["status"] == "completed"]
        cats = defaultdict(lambda: {"count": 0, "total_usdc": 0, "avg_usdc": 0})
        for b in completed:
            cat = categorize(b["title"], b.get("description", ""))
            cats[cat]["count"] += 1
            cats[cat]["total_usdc"] += b["reward_usdc"]
        for v in cats.values():
            v["avg_usdc"] = round(v["total_usdc"] / v["count"], 1) if v["count"] else 0
        # All bounties for chart
        all_by_reward = sorted(
            [{"id": b["id"], "title": b["title"][:40], "reward": b["reward_usdc"],
              "status": b["status"], "category": categorize(b["title"], b.get("description", ""))}
             for b in bounties if b["status"] not in ("cancelled",)],
            key=lambda x: x["reward"], reverse=True
        )[:20]
        return {"by_category": dict(cats), "top_by_reward": all_by_reward}


class StrategistAgent:
    id = "strategist"
    name = "Strategist"
    role = "Build Planner"
    color = "#4ecdc4"

    def assess_position(self, portfolio, competition):
        total_claimed = sum(v for k, v in competition.items() if k == "total_competitors")
        our_completion_rate = 0
        if portfolio["by_status"].get("claimed", 0) + portfolio["by_status"].get("completed", 0) > 0:
            our_completion_rate = round(
                portfolio["by_status"].get("completed", 0) /
                (portfolio["by_status"].get("completed", 0) + portfolio["by_status"].get("claimed", 0) + portfolio["by_status"].get("submitted", 0)),
                2
            )
        return {
            "our_completion_rate": our_completion_rate,
            "competitors": competition.get("total_competitors", 0),
            "pending_usdc": portfolio["submitted_pending_usdc"],
            "earned_usdc": portfolio["completed_earned_usdc"],
            "pipeline_value": portfolio["submitted_pending_usdc"] + sum(
                b["reward"] for b in portfolio["active"]
            )
        }

    def build_watch_strategy(self, categories, scan):
        best_cat = max(
            categories["by_category"].items(),
            key=lambda x: x[1]["avg_usdc"]
        ) if categories["by_category"] else ("Infrastructure", {"avg_usdc": 30})

        open_now = scan["open_unclaimed"]
        status = "MONITOR" if open_now == 0 else "ACT"
        action = (
            f"Claim immediately — {open_now} open bounties available"
            if open_now > 0 else
            f"Monitor board — watch for new {best_cat[0]} bounties (avg ${best_cat[1]['avg_usdc']} USDC)"
        )
        return {
            "status": status,
            "action": action,
            "best_category": best_cat[0],
            "best_avg_reward": best_cat[1]["avg_usdc"],
            "open_opportunities": open_now,
            "top_open": scan["open_unclaimed_list"]
        }

    def final_recommendation(self, position, watch, portfolio):
        if watch["open_opportunities"] > 0:
            rec = f"ACT NOW: {watch['open_opportunities']} unclaimed bounties. " \
                  f"Focus on {watch['best_category']} (avg ${watch['best_avg_reward']} USDC)."
        else:
            rec = (
                f"HOLD & MONITOR: ${position['pending_usdc']} pending approval. "
                f"${position['earned_usdc']} earned to date. "
                f"Board quiet — watch for new {watch['best_category']} bounties."
            )
        return {
            "recommendation": rec,
            "pipeline_value": position["pipeline_value"],
            "earned": position["earned_usdc"],
            "pending": position["pending_usdc"],
            "active_count": len(portfolio["active"]),
            "submitted_count": len(portfolio["submitted"]),
            "watch_category": watch["best_category"],
            "status": watch["status"]
        }


def run_swarm():
    scout = ScoutAgent()
    strategist = StrategistAgent()
    messages = []
    msg_id = 0

    def add_msg(frm, to, mtype, content, data=None):
        nonlocal msg_id
        msg_id += 1
        messages.append({
            "id": msg_id, "from": frm, "to": to, "type": mtype,
            "content": content, "data": data or {}, "timestamp": ts()
        })

    print("  [Scout] Fetching bounty board...")
    all_bounties = fetch_bounties()

    # MSG 1 — Scout scans board
    scan = scout.scan_board(all_bounties)
    open_str = (
        f"{scan['open_unclaimed']} unclaimed open bounties 🎯" if scan["open_unclaimed"] > 0
        else "No unclaimed open bounties — board fully claimed"
    )
    add_msg("scout", "strategist", "board_scan",
        f"Board scan complete. {scan['total']} total bounties. {open_str}. "
        f"{scan['claimed_by_others']} claimed by competitors.",
        scan
    )

    # MSG 2 — Scout analyzes portfolio
    print("  [Scout] Analyzing portfolio...")
    portfolio = scout.analyze_portfolio(all_bounties)
    add_msg("scout", "strategist", "portfolio_report",
        f"Portfolio status: {len(portfolio['active'])} active, "
        f"{len(portfolio['submitted'])} submitted (${portfolio['submitted_pending_usdc']} pending), "
        f"${portfolio['completed_earned_usdc']} earned total. "
        f"Current pipeline: #{', #'.join(str(b['id']) for b in portfolio['submitted'][:4])}.",
        portfolio
    )

    # MSG 3 — Scout analyzes competition + categories
    print("  [Scout] Analyzing competition...")
    competition = scout.analyze_competition(all_bounties)
    categories = scout.analyze_categories(all_bounties)
    best_cat = max(categories["by_category"].items(), key=lambda x: x[1]["avg_usdc"]) \
        if categories["by_category"] else ("Infrastructure", {"avg_usdc": 30, "count": 0})
    add_msg("scout", "strategist", "competitive_analysis",
        f"Competitive landscape: {competition['total_competitors']} unique builders. "
        f"Top category by reward: {best_cat[0]} (avg ${best_cat[1]['avg_usdc']} USDC, {best_cat[1]['count']} completed). "
        f"Top competitor has {competition['top_competitors'][0]['completed'] if competition['top_competitors'] else 0} completed bounties.",
        {"competition": competition, "categories": categories}
    )

    # MSG 4 — Strategist assesses our position
    position = strategist.assess_position(portfolio, competition)
    add_msg("strategist", "scout", "position_assessment",
        f"Position assessed. Pipeline: ${position['pipeline_value']} USDC. "
        f"Earned to date: ${position['earned_usdc']}. "
        f"{competition['total_competitors']} competitors active — we need to stay ahead on quality. "
        f"Scout, confirm watch priorities for next cycle.",
        position
    )

    # MSG 5 — Scout confirms watch strategy
    watch = strategist.build_watch_strategy(categories, scan)
    add_msg("scout", "strategist", "watch_strategy",
        f"Watch strategy: {watch['status']}. "
        + (f"Claiming {watch['open_opportunities']} open bounties now." if watch["open_opportunities"] > 0
           else f"Monitoring for new {watch['best_category']} bounties (avg ${watch['best_avg_reward']} USDC). "
                f"Estimated next batch: based on weekly posting pattern."),
        {"watch": watch, "top_open": watch["top_open"]}
    )

    # MSG 6 — Strategist final recommendation (broadcast)
    final = strategist.final_recommendation(position, watch, portfolio)
    add_msg("strategist", "broadcast", "recommendation",
        f"SWARM RECOMMENDATION: {final['recommendation']} "
        f"Active pipeline: ${final['pipeline_value']} USDC. "
        f"Category focus: {final['watch_category']}.",
        final
    )

    run_id = hashlib.md5(ts().encode()).hexdigest()[:8]
    print(f"  Done. {len(messages)} messages. Run ID: {run_id}")

    return {
        "run_id": run_id,
        "generated_at": ts(),
        "agents": [
            {"id": "scout", "name": "Scout", "role": "Bounty Researcher", "color": "#ff6b35"},
            {"id": "strategist", "name": "Strategist", "role": "Build Planner", "color": "#4ecdc4"},
            {"id": "broadcast", "name": "Network", "role": "Broadcast Hub", "color": "#ffe66d"}
        ],
        "messages": messages,
        "summary": {
            "total_bounties": scan["total"],
            "open_opportunities": scan["open_unclaimed"],
            "our_active": len(portfolio["active"]),
            "our_submitted": len(portfolio["submitted"]),
            "pending_usdc": portfolio["submitted_pending_usdc"],
            "earned_usdc": portfolio["completed_earned_usdc"],
            "top_opportunities": watch["top_open"],
            "recommendation": final["recommendation"],
            "categories": {k: v for k, v in categories["by_category"].items()},
            "all_bounties_chart": categories["top_by_reward"]
        }
    }


if __name__ == "__main__":
    print("🤖 Starting Owockibot Swarm...")
    result = run_swarm()
    with open("swarm-log.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"✓ Swarm log written: {len(result['messages'])} messages, run {result['run_id']}")
    print(f"  Summary: {json.dumps(result['summary'], indent=4)}")
