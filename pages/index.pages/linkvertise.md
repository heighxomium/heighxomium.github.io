---
layout: indexcategory.v2
title: ""
include_collection: linkvertise
include_on_search : false
---

{%- assign homepage = site.pages | where: "path", "index.html" | first -%}
{%- assign test_post = site.documents | where: "path", "_linkvertise/2025.05.01.001.md" | first -%}

<div style="background: yellow; border: 3px solid black; padding: 15px; margin: 20px 0; font-size: 18px; font-family: monospace;">
  <strong>DEBUG WIDGET</strong><br>
  <span style="color: red;">index.html last_modified_at:</span> 
  <code>{{ homepage.last_modified_at }}</code><br>
  <span style="color: red;">2025.05.01.001.md last_modified_at:</span> 
  <code>{{ test_post.last_modified_at }}</code>
</div>

<!-- ORIGINAL PAGE CONTENT BELOW -->
