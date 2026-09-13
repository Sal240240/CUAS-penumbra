export interface ImageCredit {
  id: string;
  file: string;
  title: string;
  author: string;
  license: string;
  licenseUrl: string;
  sourceUrl: string;
}

export const IMAGE_CREDITS: ImageCredit[] = [
  {
    id: "ottawa-skyline",
    file: "ottawa-skyline.jpg",
    title: "Ottawa skyline",
    author: "Michel Gagnon (Thecalmar)",
    license: "CC BY-SA 3.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/3.0/",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:Ottawa_skyline.jpg",
  },
  {
    id: "dji-mavic-3",
    file: "dji-mavic-3.jpg",
    title: "DJI Mavic 3",
    author: "HKesteloo",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:DJI_Mavic_3.jpg",
  },
  {
    id: "uhf-vhf-antenna",
    file: "uhf-vhf-antenna.jpg",
    title: "UHF/VHF television broadcast antenna",
    author: "Maury Markowitz",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:Old_UHF-VHF_television_antenna.jpg",
  },
  {
    id: "sdr-hackrf-pcb",
    file: "sdr-hackrf-pcb.jpg",
    title: "HackRF One software-defined radio board",
    author: "wdwd",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:SDR_HackRF_one_PCB.jpg",
  },
];

export function credit(id: string): ImageCredit {
  const c = IMAGE_CREDITS.find((i) => i.id === id);
  if (!c) throw new Error(`no image credit registered for "${id}"`);
  return c;
}
