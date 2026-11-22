import { useState } from "react";

const languages = [
  { name: "Telugu", lang: "te", phrase: "తెలుగులో" },
  { name: "Hindi", lang: "hi", phrase: "हिन्दी में" },
  { name: "English", lang: "en", phrase: "in English" },
  { name: "Tamil", lang: "ta", phrase: "தமிழில்" },
  { name: "Kannada", lang: "kn", phrase: "ಕನ್ನಡದಲ್ಲಿ" },
];

export function CallLanguages({ openingLanguage }: { openingLanguage: string }) {
  const [step, setStep] = useState(0);
  const opening = languages.find(({ name }) => name === openingLanguage)
    ?? { name: openingLanguage, lang: "en", phrase: `in ${openingLanguage}` };
  const sequence = [opening, ...languages.filter(({ name }) => name !== opening.name)];
  const description = `Starts in ${openingLanguage}. You can switch languages during the call.`;

  return (
    <span className="call-languages" title={description}>
      <span className="sr-only">{description}</span>
      <span aria-hidden="true" className="language-words"
            onAnimationIteration={() => setStep((i) => (i + 1) % sequence.length)}>
        {sequence.map(({ name, lang, phrase }, index) => (
          <span key={name} lang={lang} data-current={index === step}>{phrase}</span>
        ))}
      </span>
    </span>
  );
}
