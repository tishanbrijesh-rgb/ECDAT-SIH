// Catches React render errors and shows a fallback UI instead of a blank screen.
import React, { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error("ECDAT error boundary:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="error-boundary">
          <div className="error-boundary-card">
            <span className="error-boundary-icon">&#9888;</span>
            <h2>Something went wrong</h2>
            <p>
              A rendering error occurred in the assurance console. This has been logged for review.
            </p>
            <details>
              <summary>Technical details</summary>
              <pre>{this.state.error.message}</pre>
            </details>
            <button
              className="button"
              onClick={() => {
                this.setState({ error: null });
                window.location.reload();
              }}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
