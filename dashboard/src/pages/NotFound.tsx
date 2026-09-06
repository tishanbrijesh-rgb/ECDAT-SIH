// 404 — page not found.
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="not-found">
      <span className="not-found-code">404</span>
      <h1>Page not found</h1>
      <p className="muted">The page you're looking for doesn't exist or has been moved.</p>
      <Link className="button" to="/">
        Back to dashboard
      </Link>
    </div>
  );
}
