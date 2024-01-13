import API from "../util";

class Guild {
  id: string;
  owner_id: string;
  name: string;
  icon: string;
  splash: string;
  enabled: boolean;
  role: 'admin' | 'editor' | 'viewer';

  constructor({ id, owner_id, name, icon, splash, enabled, role }: Guild) {
    this.id = id;
    this.owner_id = owner_id;
    this.name = name;
    this.icon = icon;
    this.splash = splash;
    this.enabled = enabled;
    this.role = role;
  }

  get() {
    return {
      id: this.id,
      owner_id: this.owner_id,
      name: this.name,
      icon: this.icon,
      splash: this.splash,
      enabled: this.enabled,
      role: this.role,
    } as Guild;
  }

  get owner() {
    // TODO: Can we make this return a String? IE:
    // DeJay#1337 (ID)
    return this.owner_id;
  }

  get iconURL() {
    if(!this.icon) return 'https://cdn.discordapp.com/embed/avatars/0.png'

    return `https://cdn.discordapp.com/icons/${this.id}/${this.icon}.png`;
  }

  get splashURL() {
    return `https://cdn.discordapp.com/splashes/${this.id}/${this.splash}.png`;
  }

  async getConfig() {
    const res = await API.get(`guilds/${this.id}/config`);
    return res.data.contents;
  }

  async setConfig(config: any) {
    API.post(`guilds/${this.id}/config`, {config: config}).catch((err) => {
      console.log("Error while getting guild: " + err)
    });
  }

  static async fromID(id: string | number) {
    const res = await API.get<Guild>(`/guilds/${id}`);
    return new Guild(res.data);
  }

}

export default Guild;