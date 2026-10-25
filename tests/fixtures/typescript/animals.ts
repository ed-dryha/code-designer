export interface Walker {
  walk(): void;
}

export interface Namer {
  label(): string;
}

export interface Pet extends Namer {
  owner: string;
}

export class Animal {
  legs: number = 4;
}

export class Dog extends Animal implements Walker, Namer {
  walk(): void {}

  label(): string {
    return "dog";
  }
}
