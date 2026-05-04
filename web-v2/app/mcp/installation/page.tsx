import Link from "next/link";

export default function MCPInstallationPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-12 pt-24 sm:gap-14 sm:pt-28 md:gap-16 md:pt-32">
        <div className="flex w-full flex-col items-center text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Connect to the public endpoint
          </h1>
          <p className="mx-auto mt-5 w-[90%] max-w-full text-left text-base leading-relaxed text-slate-600 [text-wrap:pretty] dark:text-slate-400">
            A hosted instance of the unified MCP server is available at{" "}
            <a
              className="break-all font-medium text-niaid-link underline-offset-2 hover:underline"
              href="https://apps.okn.us/okn-mcp/mcp"
              rel="noopener noreferrer"
              target="_blank"
            >
              https://apps.okn.us/okn-mcp/mcp
            </a>
            . Point your MCP-capable client at that URL &mdash; no local installation required.
            Setup steps below cover the two most common clients; for additional clients and
            up-to-date screenshots, see the upstream{" "}
            <a
              className="font-medium text-niaid-link underline-offset-2 hover:underline"
              href="https://github.com/sbl-sdsc/mcp-proto-okn#installation-and-configuration"
              rel="noopener noreferrer"
              target="_blank"
            >
              mcp-proto-okn installation docs
            </a>
            .{" "}
            <Link href="/mcp" className="font-medium text-niaid-link hover:underline">
              Back to MCP server
            </Link>
          </p>
        </div>

        <div className="w-full max-w-3xl space-y-10 text-slate-700 dark:text-slate-300">
          <section className="space-y-4">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Claude Desktop
            </h2>
            <p>
              Requires a Claude Pro or Max subscription. Download Claude Desktop from{" "}
              <a
                className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                href="https://claude.ai/download"
                rel="noopener noreferrer"
                target="_blank"
              >
                claude.ai/download
              </a>
              .
            </p>
            <ol className="list-decimal space-y-2 pl-6">
              <li>
                Launch Claude Desktop and open <strong>Claude &rarr; Settings</strong>.
              </li>
              <li>
                Choose <strong>Connectors</strong> from the Settings menu and click{" "}
                <strong>Add custom connector</strong>.
              </li>
              <li>
                Enter the name <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">proto-okn</code>{" "}
                and the URL{" "}
                <code className="break-all rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                  https://apps.okn.us/okn-mcp/mcp
                </code>
                .
              </li>
              <li>
                Once <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">proto-okn</code> appears
                in the connector list, click <strong>Configure</strong> and set tool permissions
                to <strong>Always allow</strong>.
              </li>
              <li>
                Start a new chat, click the <strong>+</strong> button, toggle{" "}
                <strong>proto-okn</strong> on, and turn <strong>Web search</strong> off.
              </li>
              <li>
                Try a prompt such as: <em>Generate a table of all Proto-OKN Knowledge Graphs with
                two columns: &ldquo;KG Name&rdquo; and &ldquo;Description.&rdquo;</em>
              </li>
            </ol>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Detailed walkthrough with screenshots:{" "}
              <a
                className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                href="https://github.com/sbl-sdsc/mcp-proto-okn/blob/main/docs/claude-setup.md"
                rel="noopener noreferrer"
                target="_blank"
              >
                Claude Desktop setup guide
              </a>
              .
            </p>
          </section>

          <section className="space-y-4 border-t border-slate-200 pt-8 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              ChatGPT
            </h2>
            <p>
              Requires a ChatGPT subscription and the{" "}
              <a
                className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                href="https://chatgpt.com/"
                rel="noopener noreferrer"
                target="_blank"
              >
                ChatGPT web app
              </a>{" "}
              &mdash; the desktop app does not currently support custom MCP services.
            </p>
            <ol className="list-decimal space-y-2 pl-6">
              <li>
                Sign in at <a
                  className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                  href="https://chatgpt.com/"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  chatgpt.com
                </a>{" "}
                and click your profile name/avatar in the bottom-left corner.
              </li>
              <li>
                Choose <strong>Settings</strong> from the menu, then open{" "}
                <strong>Apps &rarr; Advanced settings</strong>.
              </li>
              <li>
                Toggle <strong>Developer mode</strong> on. MCP services only work with developer
                mode enabled.
              </li>
              <li>
                Click <strong>Create app</strong> and enter:
                <ul className="mt-2 list-disc space-y-1 pl-6">
                  <li>
                    Name: <code className="rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">proto-okn</code>
                  </li>
                  <li>
                    MCP Server URL:{" "}
                    <code className="break-all rounded bg-slate-100 px-1 py-0.5 text-sm dark:bg-slate-800">
                      https://apps.okn.us/okn-mcp/mcp
                    </code>
                  </li>
                </ul>
              </li>
              <li>
                Start a new chat, click <strong>+</strong>, choose <strong>... More &rsaquo;</strong>,
                and select <strong>proto-okn</strong>. Turn <strong>Web search</strong> off.
              </li>
              <li>
                Try a prompt such as: <em>Generate a table of all Proto-OKN Knowledge Graphs with
                two columns: &ldquo;KG Name&rdquo; and &ldquo;Description.&rdquo;</em>
              </li>
            </ol>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Detailed walkthrough with screenshots:{" "}
              <a
                className="text-blue-700 underline decoration-blue-700/30 underline-offset-2 hover:decoration-blue-700"
                href="https://github.com/sbl-sdsc/mcp-proto-okn/blob/main/docs/chatgpt-setup.md"
                rel="noopener noreferrer"
                target="_blank"
              >
                ChatGPT setup guide
              </a>
              .
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
