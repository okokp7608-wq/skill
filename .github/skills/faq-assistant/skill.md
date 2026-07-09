---
name: faq-assistant
description: Use this skill when working on the FAQ chatbot project, including updating knowledge context, adjusting prompts, or testing the web app.
---

# FAQ Assistant Skill

## Purpose
Use this skill when you need to maintain or improve the FAQ-based chatbot in this workspace.

## Project Overview
- Main application: app.py
- Frontend page: index.html
- Knowledge source: data/faq_context.xml
- Model settings: config/model_config.json

## When to Use This Skill
Apply this skill when you need to:
- add or revise FAQ knowledge
- improve the prompt or answer style
- debug the chatbot response flow
- test the app locally

## Recommended Workflow
1. Review the current FAQ data in data/faq_context.xml.
2. Check the application logic in app.py to understand how questions are processed.
3. Update the prompt or context carefully so the answer remains consistent.
4. Run the app locally and verify the response behavior.
5. Keep the output concise and relevant to the user's question.

## Good Practices
- Keep answers grounded in the provided FAQ context.
- Avoid inventing unsupported information.
- Prefer short, clear, and practical responses.
- Preserve the original structure of the project files when making changes.

## Quick Test Command
Run the app locally with:
- python app.py

## Notes
If the chatbot seems to answer incorrectly, first verify whether the issue comes from:
- missing or outdated FAQ content
- prompt wording
- model configuration
