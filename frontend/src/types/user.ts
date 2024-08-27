import API from "../util";
import Guild from "./guild";

export default class User {
  id: string;
  username: string;
  avatar: string;
  bot: boolean;
  admin: boolean;
  guilds: Guild[] | undefined;

  constructor({ id, username, avatar, bot, admin }: User) {
    this.id = id;
    this.username = username;
    this.avatar = avatar;
    this.bot = bot;
    this.admin = admin;
  }

  get() {
    return {
      id: this.id,
      username: this.username,
      avatar: this.avatar,
      bot: this.bot,
      admin: this.admin,
    } as User
  }

  async create() {
    const guild = await API.get<Guild[]>('/users/@me/guilds');
    this.guilds = guild.map((guild: Guild) => new Guild(guild));
    return this;
  }

  static async fromID(id: string | number) {
    const user = await API.get<User>(`/users/${id}`);
    return new User(user);
  }


}