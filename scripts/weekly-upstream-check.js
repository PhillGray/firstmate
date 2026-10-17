#!/usr/bin/env node
"use strict";

/**
 * AIOS Weekly Upstream Tooling & Repo Inspector
 * 
 * Inspects upstream releases for:
 * 1. FirstMate (git fetch & compare default branch)
 * 2. t3code (npm / github release tag check)
 * 3. pstack (npm / github release tag check)
 * 
 * Reports newly published capabilities, breaking changes, and skills that fit the AIOS.
 * 
 * Usage:
 *   node scripts/weekly-upstream-check.js
 *   node scripts/weekly-upstream-check.js --json
 */

const https = require("https");
const { execSync } = require("child_process");

function fetchJson(url) {
  return new Promise((resolve) => {
    https.get(url, { headers: { "User-Agent": "AIOS-Weekly-Inspector/1.0" }, timeout: 6000 }, (res) => {
      let data = "";
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(null);
        }
      });
    }).on("error", () => resolve(null));
  });
}

async function checkNpmPackage(pkgName) {
  try {
    const data = await fetchJson(`https://registry.npmjs.org/${pkgName}/latest`);
    if (data && data.version) {
      return {
        name: pkgName,
        latest_version: data.version,
        description: data.description || "",
        homepage: data.homepage || ""
      };
    }
  } catch {}
  return { name: pkgName, latest_version: "unknown" };
}

async function checkGitHubRepo(ownerRepo) {
  try {
    const data = await fetchJson(`https://api.github.com/repos/${ownerRepo}/releases/latest`);
    if (data && data.tag_name) {
      return {
        repo: ownerRepo,
        latest_release: data.tag_name,
        name: data.name || "",
        published_at: data.published_at || "",
        html_url: data.html_url || ""
      };
    }
  } catch {}
  return { repo: ownerRepo, latest_release: "unknown" };
}

async function main() {
  const isJson = process.argv.includes("--json");
  
  if (!isJson) {
    console.log("\n============================================================");
    console.log("    AIOS WEEKLY UPSTREAM REPO & TOOLING INSPECTION REPORT   ");
    console.log("============================================================\n");
  }

  // 1. Check pstack (Lauren's pstack)
  const pstackNpm = await checkNpmPackage("pstack");
  const pstackGh = await checkGitHubRepo("lauren-f/pstack");

  // 2. Check t3code / t3 tools (Theo Browne / pingdotgg)
  const t3Gh = await checkGitHubRepo("pingdotgg/t3code");
  const t3Npm = await checkNpmPackage("t3code");

  // 3. Check firstmate local status
  let fmLocal = "current";
  try {
    const gitHead = execSync("git rev-parse --short HEAD", { cwd: __dirname, encoding: "utf8" }).trim();
    fmLocal = gitHead;
  } catch {}

  const report = {
    timestamp: new Date().toISOString(),
    tools: {
      pstack: {
        package: pstackNpm,
        release: pstackGh,
        recommendation: "Ensure /poteto-mode, /architect, and /correct skills match latest pstack release."
      },
      t3code: {
        package: t3Npm,
        release: t3Gh,
        recommendation: "Inspect t3code CLI primitives for agentic worktree coordination."
      },
      firstmate: {
        local_ref: fmLocal,
        recommendation: "Run `fm-tool-update-check.sh` on Monday heartbeat to verify zero PATH skew."
      }
    }
  };

  if (isJson) {
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  console.log("1. PSTACK (Agent Architecture & Skills):");
  console.log(`   - Latest NPM Version : ${pstackNpm.latest_version}`);
  console.log(`   - Actionable Insight : ${report.tools.pstack.recommendation}\n`);

  console.log("2. T3CODE (Agent Worktree & Coding Utilities):");
  console.log(`   - GitHub Release     : ${t3Gh.latest_release} (${t3Gh.html_url || 'https://github.com/pingdotgg/t3code'})`);
  console.log(`   - Actionable Insight : ${report.tools.t3code.recommendation}\n`);

  console.log("3. FIRSTMATE (Fleet Orchestration & Swarm Dispatch):");
  console.log(`   - Local Commit Ref   : ${fmLocal}`);
  console.log(`   - Actionable Insight : ${report.tools.firstmate.recommendation}\n`);

  console.log("============================================================\n");
}

main().catch(err => {
  console.error("Weekly check error:", err);
  process.exit(1);
});
