@0x9d0356c942e754d3;
struct UserCreate {
    name     @0 :Text;
    email    @1 :Text;
    age      @2 :UInt16;
}

struct UserGet {
    id         @0 :UInt32;
    name       @1 :Text;
    email      @2 :Text;
    age        @3 :UInt16;
    isAdmin    @4 :Bool;
}
