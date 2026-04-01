const childProcess = require("child_process");
const path = require("path");
const vscode = require("vscode");

const SUPPORTED_EXTENSIONS = /\.(cpp|cc|cxx|h|hpp)$/i;

function activate(context) {
  const disposable = vscode.commands.registerCommand(
    "alignWhitespace.alignCppBlock",
    async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        return;
      }

      const document = editor.document;
      if (
        document.uri.scheme !== "file" ||
        !SUPPORTED_EXTENSIONS.test(document.fileName)
      ) {
        return;
      }

      const scriptPath = context.asAbsolutePath(
        path.join("python", "align_cpp_block.py"),
      );
      const cursorLine = editor.selection.active.line + 1;

      let formattedText;
      try {
        formattedText = await runFormatter(
          document.getText(),
          cursorLine,
          scriptPath,
        );
      } catch (error) {
        const message =
          error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`Align Whitespace: ${message}`);
        return;
      }

      if (formattedText === document.getText()) {
        return;
      }

      const fullRange = new vscode.Range(
        document.positionAt(0),
        document.positionAt(document.getText().length),
      );

      await editor.edit(
        (editBuilder) => {
          editBuilder.replace(fullRange, formattedText);
        },
        {
          undoStopBefore: true,
          undoStopAfter: true,
        },
      );
    },
  );

  context.subscriptions.push(disposable);
}

async function runFormatter(text, cursorLine, scriptPath) {
  const configured = vscode.workspace
    .getConfiguration("alignWhitespace")
    .get("pythonCommand", "python3")
    .trim();

  const candidates = [];
  if (configured) {
    candidates.push(configured);
  }
  if (!candidates.includes("python3")) {
    candidates.push("python3");
  }
  if (!candidates.includes("python")) {
    candidates.push("python");
  }

  for (const command of candidates) {
    try {
      return await execFormatter(command, scriptPath, text, cursorLine);
    } catch (error) {
      if (error && error.code === "ENOENT") {
        continue;
      }
      throw error;
    }
  }

  throw new Error(`could not launch Python. Tried: ${candidates.join(", ")}`);
}

function execFormatter(command, scriptPath, text, cursorLine) {
  return new Promise((resolve, reject) => {
    const child = childProcess.spawn(command, [scriptPath, String(cursorLine)], {
      stdio: ["pipe", "pipe", "pipe"],
    });

    const stdout = [];
    const stderr = [];

    child.on("error", reject);

    child.stdout.on("data", (chunk) => {
      stdout.push(chunk);
    });

    child.stderr.on("data", (chunk) => {
      stderr.push(chunk);
    });

    child.on("close", (code) => {
      if (code === 0) {
        resolve(Buffer.concat(stdout).toString("utf8"));
        return;
      }

      const error = Buffer.concat(stderr).toString("utf8").trim();
      reject(new Error(error || `formatter exited with code ${code}`));
    });

    child.stdin.end(text, "utf8");
  });
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
