import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "20px",
            backgroundColor: "#ffebee",
            color: "#c62828",
            minHeight: "100vh",
          }}
        >
          <h2>Something went wrong (React Error Boundary)</h2>
          <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {this.state.error && this.state.error.toString()}
          </pre>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: "12px",
              marginTop: "20px",
            }}
          >
            {this.state.error?.stack}
          </pre>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
