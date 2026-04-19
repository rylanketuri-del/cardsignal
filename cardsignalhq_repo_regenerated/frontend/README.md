# Frontend Hosting

This frontend is a static site. You can host it on Vercel, Netlify, or any static host.

## Local config

Edit `config.js` if your API is not running at `http://localhost:8000`.

## API response shape

The frontend expects:

```json
{
  "data_source": "supabase",
  "items": []
}
```

It reads the `items` array and ignores the source label for now.

## Vercel

1. Create a new Vercel project.
2. Set the project root to `frontend/`.
3. Deploy as a static site.
4. Update `config.js` to point at your hosted API URL, for example:

```js
window.CARDCHASE_API_BASE_URL = 'https://your-api.onrender.com';
```

If you want environment-driven config later, move this frontend into a small Vite or Next.js app.
