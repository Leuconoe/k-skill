# gangnamunni-clinic-search

Public Gangnam Unni clinic lookup client for the `gangnamunni-clinic-search` k-skill.

## Source

- Primary page: `https://www.gangnamunni.com/hospitals?q=<keyword>`
- Primary data path: `__NEXT_DATA__.props.pageProps.dehydratedState.queries[*].state.data.pages[*].data` for the `infinite-search-hospitals` query.
- Legacy fallback: `https://www.gangnamunni.com/search?q=<keyword>` and `props.pageProps.hospitals`.

This is an unauthenticated public web surface. No proxy or API key is required. The client does not automate login, appointments, chat, payment, reviews, or app-only flows.

## Usage

```js
const { searchClinics } = require("gangnamunni-clinic-search")

const result = await searchClinics({
  query: "강남 성형외과",
  limit: 5
})

console.log(result.items)
```

CLI:

```bash
npx gangnamunni-clinic-search "강남 성형외과" --limit 5
```

Returned clinic fields include `id`, `name`, ratings/review counts, `district`, best-effort subway/distance/coordinates, supported `languages`, public image URLs, and the public Gangnam Unni hospital page URL. Fields the upstream omits or returns as null are left out rather than fabricated.

## Failure modes

The parser classifies missing embedded Next.js data, login-required responses, CAPTCHA challenges, blocked responses, and claimed matches with no parseable hospitals separately. The last case returns `failureMode: "empty-shell"` with a structural-change warning. Result counts and clinic information are point-in-time public page data and may differ from the mobile app or logged-in experience.
