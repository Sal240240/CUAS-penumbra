import { credit } from "../data/credits";

export function CreditedImage({ id, alt, className }: { id: string; alt: string; className?: string }) {
  const c = credit(id);
  return (
    <figure className={className}>
      <img src={new URL(`../assets/images/${c.file}`, import.meta.url).href} alt={alt} loading="lazy" />
      <figcaption>
        {c.title} — {c.author}, <a href={c.licenseUrl} target="_blank" rel="noreferrer">{c.license}</a>,{" "}
        <a href={c.sourceUrl} target="_blank" rel="noreferrer">Wikimedia Commons</a>
      </figcaption>
    </figure>
  );
}
