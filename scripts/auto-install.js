const { existsSync, readFileSync } = require("node:fs");
const { spawnSync } = require("node:child_process");
const { join } = require("node:path");

const frontendDir = join(__dirname, "..", "frontend");
const packagePath = join(frontendDir, "package.json");
const nodeModules = join(frontendDir, "node_modules");
const required = ["vue", "pinia", "vue-router", "vite", "@vitejs/plugin-vue", "typescript"];

function missingDeps() {
  if (!existsSync(packagePath)) {
    return required;
  }
  const pkg = JSON.parse(readFileSync(packagePath, "utf8"));
  const declared = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
  return required.filter((name) => !declared[name] || !existsSync(join(nodeModules, name)));
}

const missing = missingDeps();
if (!existsSync(nodeModules) || missing.length > 0) {
  console.log(`[agent_browser] installing frontend deps: ${missing.join(", ") || "all"}`);
  const result = spawnSync("npm", ["install"], { cwd: frontendDir, stdio: "inherit", shell: true });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
} else {
  console.log("[agent_browser] frontend dependencies are ready");
}
