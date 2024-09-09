#!/usr/bin/env python3
"""
Simplified Lettersmith build script.
"""
from lettersmith import *

# Configuration
base_url = "http://orf.place"
site_title = "orf place"
site_description = ""
site_author = "Olive R.F."

# Load data directory
template_data = data.find("data")

# Load post docs and pipe through plugins
posts = pipe(
    docs.find("post/*.md"),
    blog.markdown_post(base_url)
    # docs.sort_by_created,
    # tuple
)

# Load root pages and pipe through plugins
pages = pipe(
    docs.find("*.md"),
    blog.markdown_page(base_url)
)

# posts_rss_doc = pipe(posts, rss.rss(
#     base_url=base_url,
#     title=site_title,
#     description=site_description,
#     author=site_author,
#     output_path="posts.xml"
# ))

# recent_posts = pipe(posts, stub.stubs, query.takes(5))

# posts_and_pages = (*posts, *pages)

context = {
    # "rss_docs": (posts_rss_doc,),
    # "recent": recent_posts,
    "site": {
        "title": site_title,
        "description": site_description,
        "author": site_author
    },
    # "data": template_data,
    "base_url": base_url
}

rendered_docs = pipe(
    (*posts, *pages), #posts_rss_doc
    jinjatools.jinja("template", context)
)

write(rendered_docs, directory="site")

print("Done!")