import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export interface SocialPostProps {
  bg: string;
  fg: string;
  accent: string;
  headlineFont: string;
  bodyFont: string;
  headline: string;
  body: string;
  stat?: string;
  label?: string;
  textAlign: "left" | "center";
  contentRatio: number;
  entrance: "spring" | "cut";
  timing: "smooth" | "staccato";
  textureType: "pencil-grid" | "halftone" | "none";
  textureOpacity: number;
}

function PencilGrid({ opacity }: { opacity: number }) {
  return (
    <AbsoluteFill
      style={{
        opacity,
        backgroundImage: `
          repeating-linear-gradient(0deg, currentColor 0px, currentColor 1px, transparent 1px, transparent 40px),
          repeating-linear-gradient(90deg, currentColor 0px, currentColor 1px, transparent 1px, transparent 40px)
        `,
        color: "rgba(0,0,0,0.15)",
      }}
    />
  );
}

function Halftone({ opacity }: { opacity: number }) {
  return (
    <AbsoluteFill
      style={{
        opacity,
        backgroundImage: `radial-gradient(circle, currentColor 1px, transparent 1px)`,
        backgroundSize: "8px 8px",
        color: "rgba(0,0,0,0.4)",
      }}
    />
  );
}

export const SocialPost: React.FC<SocialPostProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const v = height > width;
  const pad = v ? 80 : 120;

  const enter = (delay: number, distance = 40) => {
    if (props.entrance === "cut") {
      const on = frame >= delay;
      return { opacity: on ? 1 : 0, y: 0 };
    }
    const s = spring({ frame: frame - delay, fps, config: { damping: 20, mass: 0.8 } });
    return {
      opacity: interpolate(frame, [delay, delay + 20], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }),
      y: (1 - s) * distance,
    };
  };

  const accentLine = props.entrance === "cut"
    ? frame >= 5 ? 120 : 0
    : spring({ frame, fps, config: { damping: 80 } }) * 120;

  const h = enter(15);
  const b = enter(40);
  const barW = interpolate(frame, [70, 110], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: props.bg, overflow: "hidden" }}>
      {props.textureType === "pencil-grid" && <PencilGrid opacity={props.textureOpacity} />}
      {props.textureType === "halftone" && <Halftone opacity={props.textureOpacity} />}

      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at 30% 40%, ${props.accent}18 0%, transparent 60%)`,
        }}
      />

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: props.textAlign === "center" ? "center" : "flex-start",
          padding: pad,
          gap: v ? 40 : 32,
        }}
      >
        <div
          style={{
            width: accentLine,
            height: 4,
            backgroundColor: props.accent,
            borderRadius: 2,
          }}
        />

        {props.label && (
          <div
            style={{
              fontFamily: props.bodyFont,
              fontWeight: 700,
              fontSize: v ? 20 : 18,
              letterSpacing: "0.15em",
              textTransform: "uppercase" as const,
              color: props.accent,
              opacity: h.opacity,
            }}
          >
            {props.label}
          </div>
        )}

        <div
          style={{
            fontFamily: props.headlineFont,
            fontWeight: 800,
            fontSize: v ? 72 : 80,
            lineHeight: 1.1,
            color: props.fg,
            letterSpacing: "-0.02em",
            opacity: h.opacity,
            transform: `translateY(${h.y}px)`,
            maxWidth: props.textAlign === "left" ? `${props.contentRatio * 100}%` : "100%",
          }}
        >
          {props.headline}
        </div>

        {props.stat && (
          <div
            style={{
              fontFamily: props.headlineFont,
              fontWeight: 800,
              fontSize: v ? 96 : 112,
              lineHeight: 1,
              color: props.accent,
              opacity: h.opacity,
              transform: `translateY(${h.y}px)`,
            }}
          >
            {props.stat}
          </div>
        )}

        <div
          style={{
            fontFamily: props.bodyFont,
            fontWeight: 400,
            fontSize: v ? 32 : 28,
            lineHeight: 1.5,
            color: `${props.fg}99`,
            opacity: b.opacity,
            transform: `translateY(${b.y}px)`,
            maxWidth: props.textAlign === "left" ? `${props.contentRatio * 100}%` : "85%",
          }}
        >
          {props.body}
        </div>

        <div style={{ width: "100%", maxWidth: props.textAlign === "left" ? `${props.contentRatio * 100}%` : "60%" }}>
          <div style={{ height: 4, backgroundColor: `${props.fg}15`, borderRadius: 2, overflow: "hidden" }}>
            <div style={{ width: `${barW}%`, height: "100%", backgroundColor: props.accent, borderRadius: 2 }} />
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
