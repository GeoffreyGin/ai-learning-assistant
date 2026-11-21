import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

// Providers commonly use either TeX or Markdown delimiters. Leave code examples literal.
function mathMarkdown(text: string) {
  return text.split(/(```[\s\S]*?```|`[^`\n]*`)/g).map(part => {
    if (part.startsWith("`")) return part;
    return part.replace(/\\\[([\s\S]*?)\\\]/g, (_, math: string) => "\n\n$$\n" + math.trim() + "\n$$\n\n")
      .replace(/\\\(([\s\S]*?)\\\)/g, (_, math: string) => "$" + math.trim() + "$");
  }).join("");
}

export default function MathText({ text }: { text: string }) {
  return <div className="math-text"><ReactMarkdown
    remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, { trust: false }]]}
    components={{ img: ({ alt }) => <span>{alt}</span> }}
  >{mathMarkdown(text)}</ReactMarkdown></div>;
}
