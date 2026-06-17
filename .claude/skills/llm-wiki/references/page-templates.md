# Wiki Page Templates

Copy-paste templates for each page type.

---

## Source Summary

```markdown
---
title: "Article Title"
type: source
created: YYYY-MM-DD
updated: YYYY-MM-DD
source_url: "https://..."
author: "Author Name"
publication_date: YYYY-MM-DD
tags: []
---

# Article Title

## Summary
[2-3 paragraph summary of key points]

## Key Claims
- Claim 1 (with context)
- Claim 2 (with context)

## Entities Mentioned
- [[entity-name]] - role/relevance in this source

## Concepts Covered
- [[concept-name]] - how this source relates

## Notable Quotes
> "Direct quote" (context)

## Notes
[Observations, connections to other wiki knowledge]
```

---

## Entity

```markdown
---
title: "Entity Name"
type: entity
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [source-filename-1]
related: [[related-entity]], [[related-concept]]
tags: []
---

# Entity Name

## Overview
[1-2 paragraph description]

## Key Facts
- Founded/created: [date/context]
- Domain: [what they work on]
- Notable for: [key contributions]

## Relevance
[Why this entity matters]

## Related
- [[related-entity]] - relationship
- [[related-concept]] - connection

## Source History
- [[source-1]] - what this source contributed
```

---

## Concept

```markdown
---
title: "Concept Name"
type: concept
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [source-filename-1]
related: [[related-concept]], [[related-entity]]
tags: []
---

# Concept Name

## Definition
[Clear, concise definition]

## How It Works
[Explanation of mechanism or pattern]

## Key Points
- Point 1
- Point 2

## Applications
[Where/how this is used in practice]

## Related Concepts
- [[related-concept]] - how it relates

## Source History
- [[source-1]] - what this source contributed
```

---

## Comparison

```markdown
---
title: "Topic A vs Topic B"
type: comparison
created: YYYY-MM-DD
updated: YYYY-MM-DD
comparing: [[topic-a]], [[topic-b]]
sources: [source-filename-1]
tags: []
---

# Topic A vs Topic B

## Summary
[1-2 paragraph overview]

## Key Differences

| Dimension | Topic A | Topic B |
|-----------|---------|---------|
| [Dim 1] | [A] | [B] |

## When to Use Each

**Topic A when:** ...
**Topic B when:** ...

## Tradeoffs
[Nuances and edge cases]
```
