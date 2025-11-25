source "https://rubygems.org"

# Jekyll 版本
gem "jekyll", "~> 4.3"

# Just the Docs 主题
gem "just-the-docs", "~> 0.8.0"

# Jekyll 插件
group :jekyll_plugins do
  gem "jekyll-feed", "~> 0.12"
  gem "jekyll-seo-tag", "~> 2.8"
  gem "jekyll-sitemap", "~> 1.4"
end

# Ruby 3.0+ 需要
gem "webrick", "~> 1.8"

# Windows 平台需要
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

# 性能优化
gem "wdm", "~> 0.1", :platforms => [:mingw, :x64_mingw, :mswin]
