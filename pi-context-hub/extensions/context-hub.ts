import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { mkdtemp, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Type } from "typebox";

const require = createRequire(import.meta.url);

const feedbackLabels = [
	"accurate",
	"well-structured",
	"helpful",
	"good-examples",
	"outdated",
	"inaccurate",
	"incomplete",
	"wrong-examples",
	"wrong-version",
	"poorly-structured",
] as const;

const ChubSearchParams = Type.Object({
	query: Type.String({ description: "Search query, for example 'stripe checkout' or 'openai chat'." }),
	lang: Type.Optional(Type.String({ description: "Optional language filter, for example py, js, ts, python, javascript." })),
	tags: Type.Optional(Type.String({ description: "Optional comma-separated tag filter." })),
	limit: Type.Optional(Type.Integer({ description: "Maximum results to return. Defaults to 10.", minimum: 1, maximum: 50 })),
});

const ChubGetParams = Type.Object({
	id: Type.String({ description: "Context Hub entry ID, for example openai/chat or stripe/api." }),
	lang: Type.Optional(Type.String({ description: "Language variant, for example py, js, ts, python, javascript." })),
	version: Type.Optional(Type.String({ description: "Specific package/SDK version to fetch." })),
	file: Type.Optional(Type.String({ description: "Specific reference file inside the entry, for example references/auth.md." })),
	full: Type.Optional(Type.Boolean({ description: "Fetch all files for this entry." })),
});

const ChubAnnotateParams = Type.Object({
	id: Type.Optional(Type.String({ description: "Context Hub entry ID. Required for set, get, and clear; ignored for list." })),
	note: Type.Optional(Type.String({ description: "Concise local note/gotcha. Required when action is set." })),
	action: Type.Optional(StringEnum(["set", "get", "clear", "list"] as const)),
});

const ChubFeedbackParams = Type.Object({
	id: Type.String({ description: "Context Hub entry ID to rate." }),
	rating: StringEnum(["up", "down"] as const),
	comment: Type.Optional(Type.String({ description: "Optional non-sensitive feedback comment." })),
	labels: Type.Optional(Type.Array(StringEnum(feedbackLabels), { description: "Optional feedback labels." })),
	lang: Type.Optional(Type.String({ description: "Optional language variant the feedback applies to." })),
	file: Type.Optional(Type.String({ description: "Optional specific file the feedback applies to." })),
});

function resolveChubCommand(): { command: string; baseArgs: string[]; source: string } {
	const explicitBin = process.env.PI_CONTEXT_HUB_CHUB_BIN?.trim();
	if (explicitBin) {
		return { command: explicitBin, baseArgs: [], source: "env" };
	}

	try {
		const binPath = require.resolve("@aisuite/chub/bin/chub");
		return { command: process.execPath, baseArgs: [binPath], source: "package" };
	} catch (error) {
		if (process.env.PI_CONTEXT_HUB_ALLOW_GLOBAL_CHUB === "1") {
			return { command: "chub", baseArgs: [], source: "path" };
		}
		throw new Error(
			`Could not resolve @aisuite/chub from the pi-context-hub package. Run npm install in the package directory, reinstall the Pi package, set PI_CONTEXT_HUB_CHUB_BIN to a chub executable, or set PI_CONTEXT_HUB_ALLOW_GLOBAL_CHUB=1 to explicitly allow PATH fallback. Original error: ${error instanceof Error ? error.message : String(error)}`,
		);
	}
}

function cleanOptionalString(value: string | undefined): string | undefined {
	const trimmed = value?.trim();
	return trimmed ? trimmed : undefined;
}

function validateRelativeFilePath(file: string | undefined): string | undefined {
	const cleaned = cleanOptionalString(file);
	if (!cleaned) return undefined;
	if (cleaned.startsWith("/") || cleaned.includes("..") || cleaned.includes("\\")) {
		throw new Error(`Invalid file path: ${cleaned}. Use a relative file path inside the Context Hub entry.`);
	}
	return cleaned;
}

function requireEntryId(id: string | undefined, action: string): string {
	const cleaned = cleanOptionalString(id);
	if (!cleaned) throw new Error(`id is required when chub_annotate action is ${action}`);
	return cleaned;
}

function formatExecFailure(command: string, args: string[], code: number | undefined, stderr: string): string {
	const rendered = [command, ...args].join(" ");
	const suffix = stderr.trim() ? `\n\n${stderr.trim()}` : "";
	return `chub command failed${code === undefined ? "" : ` with exit code ${code}`}: ${rendered}${suffix}`;
}

async function writeTempOutput(text: string): Promise<string> {
	const dir = await mkdtemp(join(tmpdir(), "pi-context-hub-"));
	const file = join(dir, "chub-output.txt");
	await writeFile(file, text, "utf8");
	return file;
}

function splitCommandLine(input: string): string[] {
	const args: string[] = [];
	let current = "";
	let quote: '"' | "'" | undefined;
	let escaping = false;

	for (const char of input) {
		if (escaping) {
			current += char;
			escaping = false;
			continue;
		}
		if (char === "\\" && quote !== "'") {
			escaping = true;
			continue;
		}
		if ((char === '"' || char === "'") && (!quote || quote === char)) {
			quote = quote ? undefined : char;
			continue;
		}
		if (/\s/.test(char) && !quote) {
			if (current) args.push(current);
			current = "";
			continue;
		}
		current += char;
	}

	if (escaping) current += "\\";
	if (quote) throw new Error(`Unclosed quote in /chub command: ${quote}`);
	if (current) args.push(current);
	return args;
}

export default function contextHubExtension(pi: ExtensionAPI) {
	async function runChub(args: string[], signal?: AbortSignal, timeout = 60_000) {
		const resolved = resolveChubCommand();
		const fullArgs = [...resolved.baseArgs, ...args];
		const result = await pi.exec(resolved.command, fullArgs, { signal, timeout });
		if (result.code !== 0) {
			throw new Error(formatExecFailure(resolved.command, fullArgs, result.code, result.stderr || ""));
		}
		return { ...result, chubSource: resolved.source };
	}

	pi.registerTool({
		name: "chub_search",
		label: "Chub Search",
		description: "Search Context Hub for current, LLM-optimized API, SDK, library, and agent-skill documentation.",
		promptSnippet: "Search Context Hub for current API/SDK/library documentation before coding against external dependencies.",
		promptGuidelines: [
			"Use chub_search before writing code against third-party APIs, SDKs, or libraries when current API shape, package version, or examples matter.",
			"After chub_search finds a relevant entry, use chub_get to fetch the actual docs before implementing.",
		],
		parameters: ChubSearchParams,
		async execute(_toolCallId, params, signal) {
			const args = ["search", params.query, "--json", "--limit", String(params.limit ?? 10)];
			const lang = cleanOptionalString(params.lang);
			const tags = cleanOptionalString(params.tags);
			if (lang) args.push("--lang", lang);
			if (tags) args.push("--tags", tags);

			const result = await runChub(args, signal, 45_000);
			return {
				content: [{ type: "text", text: result.stdout.trim() || "No Context Hub results." }],
				details: { args, source: result.chubSource },
			};
		},
	});

	pi.registerTool({
		name: "chub_get",
		label: "Chub Get",
		description: "Fetch a Context Hub doc or skill by ID, with optional language/version/reference-file selection.",
		promptSnippet: "Fetch Context Hub docs by ID, language, version, reference file, or full entry.",
		promptGuidelines: [
			"Use chub_get after chub_search and read the returned documentation before coding against the external API or SDK.",
			"Prefer a specific chub_get lang argument, such as py, js, or ts, when the target project language is known.",
			"If chub_get output lists additional files relevant to the task, call chub_get again with file rather than guessing from the overview.",
		],
		parameters: ChubGetParams,
		async execute(_toolCallId, params, signal) {
			const args = ["get", params.id];
			const lang = cleanOptionalString(params.lang);
			const version = cleanOptionalString(params.version);
			const file = validateRelativeFilePath(params.file);
			if (lang) args.push("--lang", lang);
			if (version) args.push("--version", version);
			if (file) args.push("--file", file);
			if (params.full) args.push("--full");

			const result = await runChub(args, signal, params.full ? 120_000 : 60_000);
			return {
				content: [{ type: "text", text: result.stdout.trim() || `Fetched ${params.id}, but chub returned no content.` }],
				details: { args, source: result.chubSource },
			};
		},
	});

	pi.registerTool({
		name: "chub_annotate",
		label: "Chub Annotate",
		description: "Create, read, clear, or list local Context Hub annotations that persist across Pi sessions.",
		promptSnippet: "Save concise local Context Hub gotchas with annotations for future sessions.",
		promptGuidelines: [
			"Use chub_annotate to save concise, non-sensitive gotchas discovered while using an API, SDK, or library when the note would help future sessions.",
			"Do not put secrets, private source code, credentials, or sensitive architecture details in chub_annotate notes.",
		],
		parameters: ChubAnnotateParams,
		async execute(_toolCallId, params, signal) {
			const action = params.action ?? (params.note ? "set" : "get");
			let args: string[];
			switch (action) {
				case "list":
					args = ["annotate", "--list"];
					break;
				case "clear":
					args = ["annotate", requireEntryId(params.id, action), "--clear"];
					break;
				case "get":
					args = ["annotate", requireEntryId(params.id, action)];
					break;
				case "set": {
					const note = cleanOptionalString(params.note);
					if (!note) throw new Error("note is required when action is set");
					args = ["annotate", requireEntryId(params.id, action), note];
					break;
				}
			}

			const result = await runChub(args, signal, 30_000);
			return {
				content: [{ type: "text", text: result.stdout.trim() || "Annotation command completed." }],
				details: { args, source: result.chubSource },
			};
		},
	});

	pi.registerTool({
		name: "chub_feedback",
		label: "Chub Feedback",
		description: "Send non-sensitive up/down feedback about a Context Hub doc or skill to maintainers.",
		promptSnippet: "Send up/down feedback for Context Hub entries when the user asks or after docs prove helpful/outdated.",
		promptGuidelines: [
			"Use chub_feedback only for non-sensitive feedback about Context Hub documentation quality; never include secrets, private code, or private architecture details.",
			"Prefer asking the user before sending chub_feedback unless the user explicitly requested feedback be sent.",
		],
		parameters: ChubFeedbackParams,
		async execute(_toolCallId, params, signal) {
			const args = ["feedback", params.id, params.rating];
			const comment = cleanOptionalString(params.comment);
			const labels = params.labels ?? [];
			const lang = cleanOptionalString(params.lang);
			const file = validateRelativeFilePath(params.file);
			if (comment) args.push(comment);
			for (const label of labels) args.push("--label", label);
			if (lang) args.push("--lang", lang);
			if (file) args.push("--file", file);

			const result = await runChub(args, signal, 30_000);
			return {
				content: [{ type: "text", text: result.stdout.trim() || "Feedback sent." }],
				details: { args, source: result.chubSource },
			};
		},
	});

	pi.registerCommand("chub", {
		description: "Run Context Hub CLI: /chub search openai, /chub get openai/chat --lang py, /chub update",
		handler: async (args, ctx) => {
			const argv = args.trim().length ? splitCommandLine(args.trim()) : ["--help"];
			try {
				const result = await runChub(argv, undefined, 60_000);
				const text = (result.stdout || result.stderr || "chub command completed").trim();
				if (text.length > 4_000) {
					const file = await writeTempOutput(text);
					ctx.ui.notify(`${text.slice(0, 1_500)}\n…\n\nFull chub output written to ${file}`, "info");
				} else {
					ctx.ui.notify(text, "info");
				}
			} catch (error) {
				ctx.ui.notify(error instanceof Error ? error.message : String(error), "error");
			}
		},
	});
}
