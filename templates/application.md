---
company: {{ company }}
title: "{{ title }}"
status: {{ status }}
score: {{ score }}
applied_date: {{ applied_date or '' }}
url: {{ url }}
job_id: {{ job_id }}
tags: [job-application, {{ company | lower | replace(' ', '-') }}]
---

# {{ company }} — {{ title }}

## Status: {{ status | capitalize }}
{% if applied_date %}- **Applied:** {{ applied_date }}{% endif %}
- **Status updated:** {{ status_updated_at or 'N/A' }}

## Contacts

## Salary & Compensation
{{ salary_notes or '' }}

## Interview Prep

## Notes

## Match Analysis
{% if score != 'N/A' %}Score: {{ score }} | [View Listing]({{ url }})

{% if key_requirements %}Key requirements:
{% for req in key_requirements %}- {{ req }}
{% endfor %}{% endif %}

{% if match_reason %}Why this matches:
{{ match_reason }}{% endif %}
{% else %}No match analysis available — job was tracked directly.

[View Listing]({{ url }})
{% endif %}
