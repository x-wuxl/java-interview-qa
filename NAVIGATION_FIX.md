# 导航栏修复说明

## 问题

部署到 GitHub Pages 后，左侧导航栏不显示。

## 原因

GitHub Pages 使用 `remote_theme` 时，必须在 `plugins` 列表中明确声明 `jekyll-remote-theme` 插件。

## 修复内容

### 1. _config.yml

添加了 `jekyll-remote-theme` 插件：

```yaml
plugins:
  - jekyll-feed
  - jekyll-seo-tag
  - jekyll-sitemap
  - jekyll-remote-theme  # ← 新增
```

### 2. Gemfile

添加了 `jekyll-remote-theme` gem：

```ruby
group :jekyll_plugins do
  gem "jekyll-feed", "~> 0.12"
  gem "jekyll-seo-tag", "~> 2.8"
  gem "jekyll-sitemap", "~> 1.4"
  gem "jekyll-remote-theme", "~> 0.4"  # ← 新增
end
```

## 部署步骤

```bash
git add _config.yml Gemfile
git commit -m "修复导航栏显示问题 - 添加 jekyll-remote-theme 插件"
git push origin main
```

GitHub Pages 将在 2-5 分钟内重新构建网站，之后左侧导航栏应该会正常显示。

## 预期效果

修复后，网站将显示：
- ✅ 左侧导航栏（包含20个技术分类）
- ✅ 搜索功能
- ✅ 面包屑导航
- ✅ 分类展开/折叠功能

## 如果问题仍然存在

请检查：
1. GitHub Pages 是否已完成重新构建（查看仓库的 Actions 标签）
2. 浏览器缓存是否已清除（Ctrl+F5 强制刷新）
3. _config.yml 中的 remote_theme 配置是否正确
