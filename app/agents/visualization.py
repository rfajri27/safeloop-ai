"""Graph visualization utilities for LangGraph agents.

Provides HTML rendering for Mermaid graph visualization.
"""
from langgraph.graph.state import CompiledStateGraph


def render_graph_html(graph: CompiledStateGraph, title: str) -> str:
    """Generate HTML page with Mermaid visualization for a LangGraph.
    
    Creates a self-contained HTML page that renders the graph
    using Mermaid.js CDN. No server-side dependencies required.
    
    Args:
        graph: Compiled LangGraph StateGraph
        title: Title to display on the page
    
    Returns:
        Complete HTML string ready to serve
    
    Example:
        html = render_graph_html(my_graph, "My Agent Workflow")
        return HTMLResponse(content=html)
    """
    mermaid_graph = graph.get_graph().draw_mermaid()
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background-color: #f0f2f5;
            }}
            .container {{
                background: white;
                padding: 2rem;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 90vw;
            }}
            h3 {{
                margin-bottom: 24px;
                color: #1a1a2e;
                font-weight: 600;
            }}
            .mermaid {{
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h3>{title}</h3>
            <pre class="mermaid">
            {mermaid_graph}
            </pre>
        </div>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
    </body>
    </html>
    """
