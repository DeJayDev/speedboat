import API from "../util";
import Guild from "./guild";

export default class User {
  id: string;
  username: string;
  discriminator: string;
  avatar: string;
  bot: boolean;
  admin: boolean;
  guilds: Guild[] | undefined;

  constructor({ id, username, discriminator, avatar, bot, admin }: User) {
    this.id = id;
    this.username = username;
    this.discriminator = discriminator;
    this.avatar = avatar;
    this.bot = bot;
    this.admin = admin;
  }

  get() {
    return {
      id: this.id,
      username: this.username,
      discriminator: this.discriminator,
      avatar: this.avatar,
      bot: this.bot,
      admin: this.admin,
    } as User
  }

  async create() {
    const res = await API.get<Guild[]>('/users/@me/guilds');
    this.guilds = res.data.map((guild: Guild) => new Guild(guild));
    return this;
  }

  static async fromID(id: string | number) {
    const res = await API.get<User>(`/users/${id}`);
    return new User(res.data);
  }


}