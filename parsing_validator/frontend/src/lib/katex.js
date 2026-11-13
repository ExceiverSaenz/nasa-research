// The pinned KaTeX (the same file the service runs through Node to compute the stored MathML, ADR-006). It is a classic
// script copied into the build as ./vendor/katex.min.js and loaded the first time a preview is needed.
let loading = null;

export function loadKatex() {
  if (window.katex) return Promise.resolve(window.katex);
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = new URL('./vendor/katex.min.js', document.baseURI).href;
      script.onload = () => resolve(window.katex);
      script.onerror = () => { loading = null; reject(new Error('The LaTeX preview could not be loaded')); };
      document.head.appendChild(script);
    });
  }
  return loading;
}

// MathML for one source, or the error KaTeX reports (exactly the options of the service, so the preview and the stored MathML are the same markup; CSS shows it inline).
export function toMathML(katex, source) {
  try {
    const html = katex.renderToString(source, { output: 'mathml', throwOnError: true, displayMode: true, strict: 'ignore' });
    return { html, error: null };
  } catch (error) {
    return { html: null, error: String(error.message || error).replace(/^KaTeX parse error:\s*/, '') };
  }
}
