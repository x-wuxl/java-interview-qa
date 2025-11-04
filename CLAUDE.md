# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Jekyll-based static website for Java backend interview questions and answers, deployed on GitHub Pages. The site is organized as a knowledge base with categorized interview questions covering topics like Java fundamentals, collections, concurrency, JVM, Spring framework, databases, middleware, distributed systems, design patterns, and algorithms.

**Website URL**: https://x-wuxl.github.io/java-interview-qa

## Development Commands

### Prerequisites
- Ruby >= 2.5
- RubyGems
- Bundler

### Initial Setup
```bash
# Install dependencies
bundle install
```

### Running Locally
```bash
# Start local development server (default: http://localhost:4000)
bundle exec jekyll serve

# With live reload for automatic browser refresh
bundle exec jekyll serve --livereload

# Alternative shorthand (if Jekyll is globally installed)
jekyll serve
```

### Building the Site
```bash
# Build static site to _site/ directory
bundle exec jekyll build
```

## Architecture and Structure

### Jekyll Site Architecture

This is a standard Jekyll site with the following key components:

- **_config.yml**: Main Jekyll configuration (site metadata, plugins, build settings)
- **_layouts/**: Page layout templates using Liquid templating
  - `default.html`: Base layout with header/footer
  - `home.html`: Homepage with category grid and recent posts
  - `post.html`: Individual interview question/answer display with navigation and metadata
- **_includes/**: Reusable components (header.html, footer.html)
- **_posts/**: Interview question articles in Markdown format (currently empty but structured for future content)
- **assets/css/**: Styling (style.css for main styles, syntax.css for code highlighting)

### Content Organization

**Interview questions** are stored as Markdown files in `_posts/` directory following Jekyll's naming convention:
```
YYYY-MM-DD-title.md
```

Each post requires YAML front matter with:
```yaml
---
layout: post
title: "Question Title"
date: YYYY-MM-DD
description: "Question description"
author: "wuxl"
categories: [Category Name]
tags: [tag1, tag2, tag3]
---
```

### Standard Category Names

Use these exact category names for consistency:
- `Java基础`
- `集合框架`
- `并发编程`
- `JVM`
- `Spring框架`
- `数据库`
- `中间件`
- `分布式`
- `设计模式`
- `算法与数据结构`

### Template System

The site uses **Liquid** templating engine:
- Posts are accessed via `site.posts` collection
- Learning path order is defined in `_data/home_order.yml` (auto-generated from `学习路径排序_优化版.md`)
- Homepage displays all questions organized by 17 categories with subsections
- Navigation between posts uses global question order (1-461)

## Adding New Interview Questions

1. Create file in `_posts/` with format: `YYYY-MM-DD-descriptive-title.md`
2. Add required front matter (layout, title, date, categories, tags)
3. Write content using Markdown with proper structure:
   - ## 问题 (Question section)
   - ## 答案 (Answer section)
4. Use code blocks with language specification for syntax highlighting:
   ````markdown
   ```java
   // code here
   ```
   ````
5. Add the question to `学习路径排序_优化版.md` in the appropriate position
6. Run `python scripts/generate_home_data.py` to update the homepage data

## Technology Stack

- **Jekyll 4.3**: Static site generator
- **Liquid**: Templating engine
- **Kramdown**: Markdown processor (configured in _config.yml)
- **Rouge**: Code syntax highlighter
- **GitHub Pages**: Hosting platform
- **Plugins**: jekyll-feed, jekyll-seo-tag (GitHub Pages compatible)

## Important Notes

- The `_posts/` directory structure exists but is currently empty; posts should be added there
- The site is configured for GitHub Pages deployment with baseurl and url in _config.yml
- Windows-specific gems are included in Gemfile (tzinfo, wdm for performance)
- Jekyll automatically rebuilds when files change during `jekyll serve`
- Built files go to `_site/` directory (excluded from git via .gitignore)
