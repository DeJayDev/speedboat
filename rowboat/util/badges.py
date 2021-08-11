# Original Credit to EJH2
# Source: https://gist.github.com/EJH2/c91d332237de6f8ee20fd69026e0f819/28daeb45e5ab7538129818593c32bfbfa0371466

class FlagValue:
    def __init__(self, func):
        self.flag = func(None)
        self.__doc__ = func.__doc__

    def __get__(self, instance, owner):
        return instance._has_flag(self.flag)


class UserFlags:
    def __init__(self, value: int = 0):
        self.value = value

    def __repr__(self):
        return '<%s value=%s>' % (self.__class__.__name__, self.value)

    def __iter__(self):
        for name, value in self.__class__.__dict__.items():
            if isinstance(value, FlagValue) and self._has_flag(value.flag):
                yield name

    def _has_flag(self, o):
        return (self.value & o) == o

    @FlagValue
    def discord_employee(self):
        return 1 << 0

    @FlagValue
    def discord_partner(self):
        return 1 << 1

    @FlagValue
    def hypesquad_events(self):
        return 1 << 2

    @FlagValue
    def bug_hunter_one(self):
        return 1 << 3

    @FlagValue
    def mfa_sms(self):
        return 1 << 4

    @FlagValue
    def premium_promo_dismissed(self):
        return 1 << 5

    @FlagValue
    def house_bravery(self):
        return 1 << 6

    @FlagValue
    def house_brilliance(self):
        return 1 << 7

    @FlagValue
    def house_balance(self):
        return 1 << 8

    @FlagValue
    def early_supporter(self):
        return 1 << 9

    @FlagValue
    def team_user(self):
        return 1 << 10

    @FlagValue
    def system(self):
        return 1 << 12

    @FlagValue
    def unread_sys_msg(self):
        return 1 << 13

    @FlagValue
    def bug_hunter_two(self):
        return 1 << 14

    @FlagValue
    def underage_deleted(self):
        return 1 << 15

    @FlagValue
    def verified_bot(self):
        return 1 << 16

    @FlagValue
    def verified_dev(self):
        return 1 << 17

    @FlagValue
    def certified_moderator(self):
        return 1 << 18
