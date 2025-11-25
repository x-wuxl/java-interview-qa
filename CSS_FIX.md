# CSS 404 问题修复

## 问题
部署后CSS文件显示404错误。

## 原因
GitHub Actions workflow 中的 `baseurl` 使用了错误的变量 `${{ steps.pages.outputs.base_path }}`，导致路径不正确。

## 修复
将 workflow 中的 baseurl 硬编码为正确的值：`/java-interview-qa`

## 部署步骤

```bash
# 提交修复
git add .github/workflows/pages.yml
git commit -m "修复 CSS 404 - 更正 baseurl 配置"
git push origin main
```

## 等待
- 等待 GitHub Actions 重新构建（2-3 分钟）
- 访问 https://github.com/x-wuxl/java-interview-qa/actions 查看进度

## 验证
访问 https://x-wuxl.github.io/java-interview-qa/ 应该能看到：
- ✅ CSS 正确加载
- ✅ 左侧导航栏显示
- ✅ Just the Docs 主题样式

---

**重要提醒**：确保在 GitHub 仓库设置中已经将 Pages Source 设置为 "GitHub Actions"
