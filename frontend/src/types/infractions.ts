import User from "./user";

interface Infraction {
  id: string;
  guild_id: string;
  user: User;
  actor: User;

  type: InfractionType;
  reason: string;

  expires_at: string;
  created_at: string;

  active: boolean;
  messaged: boolean;
}

interface InfractionType {
  id: string; // I think
  name: string;
}

export default Infraction;