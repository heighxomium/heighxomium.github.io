---
layout: default
title: All Posts
permalink: /posts/
---

Here are all the blog posts:

<ul>
{% for post in site.posts %}
  <li>
    <a href="{{ post.url }}">{{ post.title }}</a>
    <small>({{ post.date | date: "%B %d, %Y" }})</small>
  </li>
{% endfor %}
</ul>
