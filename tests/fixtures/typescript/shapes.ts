export interface Shape {
  name: string;
  area(): number;
}

export enum Kind {
  Round,
  Flat,
}

export abstract class Base implements Shape {
  name: string = "base";
  private static count: number = 0;
  readonly id = 1;

  constructor(name: string) {
    this.name = name;
  }

  abstract area(): number;

  scale(f: number): number;
  scale(f: string): number;
  scale(f: any): number {
    return 1;
  }

  handler = (x: number) => x + 1;
}

export function makeBase(name: string): Base {
  return null as any;
}
