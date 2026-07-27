import { access, readFile } from "node:fs/promises";
import { constants } from "node:fs";

const requiredDocuments = [
  { path: "AGENTS.md", phrases: ["文档与交付门禁", "npm run check"] },
  { path: "开发文档.md", phrases: ["目标架构", "NormalizedArticle", "工程约束"] },
  { path: "数据模型与接口.md", phrases: ["核心数据表", "/api/v1", "采集链路"] },
  { path: "前端主题规范.md", phrases: ["登录页固定构图", "动效与可访问性", "响应式"] },
  { path: "测试文档.md", phrases: ["前端测试", "后端测试", "验收门槛"] },
];

const requiredPrototypeFiles = [
  ".openai/hosting.json",
  "worker/index.js",
  "scripts/prepare-sites-build.mjs",
  "tests/sites-worker.test.mjs",
];

async function assertReadable(path) {
  try {
    await access(path, constants.R_OK);
  } catch {
    throw new Error(`缺少必需文件：${path}`);
  }
}

async function verifyDocument({ path, phrases }) {
  await assertReadable(path);
  const text = await readFile(path, "utf8");
  const missing = phrases.filter((phrase) => !text.includes(phrase));
  if (missing.length) {
    throw new Error(`${path} 缺少规范章节：${missing.join("、")}`);
  }
}

try {
  await Promise.all(requiredPrototypeFiles.map(assertReadable));
  await Promise.all(requiredDocuments.map(verifyDocument));
  console.log("项目契约检查通过：规范文档和托管文件完整。");
} catch (error) {
  console.error(`项目契约检查失败：${error.message}`);
  process.exitCode = 1;
}
