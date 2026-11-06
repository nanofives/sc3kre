// SC3KU Apache Flyover v0.9 directional flight test. Copyright (c) 2026 Throne Vintage Tech.
// MIT licensed. Separate, nondestructive visual event; no game bytes are patched.
#include "cGZMessage.h"
#include "cIGZApp.h"
#include "cIGZCheatCodeManager.h"
#include "cIGZCOM.h"
#include "cIGZFrameWork.h"
#include "cIGZMessageServer.h"
#include "cIGZString.h"
#include "cRZAutoRefCount.h"
#include "cRZBaseString.h"
#include "cRZMessageCOMDirector.h"
#include "cISC3App.h"
#include "cISC3City.h"
#include "cISC3ZoneLayer.h"
#include "cISC3OccupantManager.h"
#include "cISC3Occupant.h"
#include "cISC3CrimeLayer.h"
#include "cISC3ResidentialLayer.h"
#include "cISC3BuildingLayer.h"
#include <vector>
#include "FlightMotion.h"
#include "GZServPtrs.h"
#include <windows.h>
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
// The SDK forward-declares this game's two-coordinate value type.
struct sIGZPointXZUint32 { uint32_t x,z; };

namespace {
constexpr uint32_t directorID=0x739A61A1, onID=0x739A61A2, offID=0x739A61A3;
constexpr uint32_t pilotID=0x739A61A4, autoID=0x739A61A5;
constexpr uint32_t upID=0x739A61A6, downID=0x739A61A7;
constexpr uint32_t leftID=0x739A61A8, rightID=0x739A61A9;
constexpr uint32_t patrolID=0x739A61AA, turnID=0x739A61AB;
constexpr uint32_t cheatMessage=0x230E27AC, preCity=0x311FDAE5, postCity=0x511FDAE5;
constexpr uint32_t group=0x739A61A0, attrBase=0xFFFA9000;
constexpr uint32_t indexedSegment=0x80C381D7, segmentIID=0xC019963E;
constexpr uint32_t attrType=0x6300, attrIID=0x6100;
struct Key { uint32_t type, group, instance; };
struct AircraftSprite { void* ptr=nullptr; int32_t x=0,z=0,altitude=0; uint8_t alpha=255; };
template<typename F> F V(void* p,size_t slot){
    if(!p)return nullptr;
    void*** table=reinterpret_cast<void***>(p);
    return *table?reinterpret_cast<F>((*table)[slot]):nullptr;
}
bool At(void* p,size_t slot,HMODULE mod,uintptr_t offset){
    return mod && V<void*>(p,slot)==reinterpret_cast<uint8_t*>(mod)+offset;
}
void Release(void* p){using Fn=uint32_t(__thiscall*)(void*);auto fn=V<Fn>(p,2);if(fn)fn(p);}
bool App(cIGZFrameWork* fw,cRZAutoRefCount<cISC3App>& out){
    cIGZApp* base=fw?fw->Application():nullptr;
    return base && base->QueryInterface(GZIID_cISC3App,out.AsPPVoid());
}
void* Map(cISC3App* app){
    if(!app)return nullptr;
    using Get=void*(__thiscall*)(void*);
    void* window=static_cast<void*>(app->GetISC3WinCityView());
    auto iso=V<Get>(window,38);
    void* view=iso?iso(window):nullptr;
    auto map=V<Get>(view,38);
    return map?map(view):nullptr;
}
bool ValidMap(void* map){
    HMODULE spr=GetModuleHandleA("SIMSPR.DLL");
    if(!spr)return false;
    const auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(spr);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0)return false;
    const auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS32*>(reinterpret_cast<const uint8_t*>(spr)+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE && nt->FileHeader.TimeDateStamp==0x38FD55E5
        && nt->OptionalHeader.SizeOfImage==0x7D000
        && At(map,64,spr,0xE52A) && At(map,65,spr,0xE6D5) && At(map,67,spr,0xE83D)
        && At(map,94,spr,0x10142);
}
bool Ground(void* map,int x,int z,int w,int h,int32_t& altitude){
    if(!map || x<0 || z<0 || x>=w || z>=h)return false;
    const auto* bytes=static_cast<const uint8_t*>(map);
    if(*reinterpret_cast<const uint32_t*>(bytes+0x14)!=unsigned(w) ||
       *reinterpret_cast<const uint32_t*>(bytes+0x18)!=unsigned(h))return false;
    auto rows=*reinterpret_cast<const uint8_t* const* const*>(bytes+0x24);
    if(!rows || !rows[x])return false;
    altitude=int32_t(rows[x][z*20+11])*256;
    return true;
}
bool Ticker(cISC3App* app,const char* title){
    auto* cheats=app?app->GetCheatCodeManager():nullptr;
    const uintptr_t base=reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr));
    if(!cheats || base!=0x400000)return false;
    const auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return false;
    const auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
    static constexpr uint8_t ctor[]={0xb8,0x68,0x10,0x4c,0x00,0xe8,0x70,0xd9,0x0a,0x00,0x53,0x56,0x57,0x8b,0x7d,0x08,0x8b,0xf1};
    static constexpr uint8_t dtor[]={0x8b,0x11,0x8b,0x41,0x08,0x2b,0xc2,0x85,0xd2,0x74,0x0d,0x85,0xc0,0x74,0x09,0x50,0x52,0xe8,0x3a,0x01,0x00,0x00,0x59,0x59,0xc3};
    if(nt->FileHeader.TimeDateStamp!=0x63732172 || nt->OptionalHeader.SizeOfImage!=0x11B000 ||
       std::memcmp(reinterpret_cast<void*>(base+0x6f26),ctor,sizeof(ctor)) ||
       std::memcmp(reinterpret_cast<void*>(base+0x204b),dtor,sizeof(dtor)))return false;
    std::string line="simon says ";line+=title;
    cRZBaseString source(line.c_str());
    struct NativeString {
        std::array<uint32_t,5> data{};
        explicit NativeString(const cIGZString& value){
            using Fn=void*(__thiscall*)(void*,const cIGZString&);
            reinterpret_cast<Fn>(0x406f26)(data.data(),value);
        }
        ~NativeString(){using Fn=void(__thiscall*)(void*);reinterpret_cast<Fn>(0x40204b)(data.data()+1);}
        const cIGZString& value()const{return *reinterpret_cast<const cIGZString*>(data.data());}
    } native(source);
    uint32_t id=0;
    if(!cheats->DoesCheatCodeMatch(native.value(),id) || id!=0x03546e10)return false;
    cheats->SendCheatNotifications(native.value(),id);
    return true;
}

cIGZFrameWork* framework=nullptr;
void* segment=nullptr;
void* resourceManager=nullptr;
bool registered=false,playing=false,blocked=false,cityReady=false,patrolMode=false;
constexpr unsigned attributeCount=34;
std::array<void*,attributeCount> attributes{};
std::array<std::array<bool,attributeCount>,5> pinned{};
std::array<AircraftSprite,attributeCount*3> sprites{};
void* spriteMap=nullptr;
void* cityIdentity=nullptr;
UINT_PTR timer=0;
std::string logPath;
void Log(const char* line){
    if(logPath.empty())return;
    if(FILE* f=std::fopen(logPath.c_str(),"a")){
        std::fprintf(f,"APACHE_V09_TEST|%llu|%s\n",static_cast<unsigned long long>(GetTickCount64()),line);
        std::fclose(f);
    }
}
ULONGLONG startTime=0,lastTick=0,nextDraw=0;
ULONGLONG nextTicker=0;
double cx=0,cz=0,travel=0;
double manualX=0,manualZ=0;
bool pilotMode=false,returning=false;
double manualYaw=0;
std::array<double,3> aircraftYaw{};
bool headingLocked=false,nudgeActive=false,motionReady=false;
std::array<flight::Body,3> aircraft{};
std::array<double,3> aircraftAltitude{};
double formationAngle=0,formationSpread=3.0;
int facingCandidate=-1;
ULONGLONG facingSince=0;
bool turnLeftHeld=false,turnRightHeld=false;
bool patrolReady=false;
int headingX=1,headingZ=0;
double waypointX=0,waypointZ=0;
ULONGLONG nextWaypoint=0;
ULONGLONG nextDensityCheck=0;
bool narrowFormation=false;
uint32_t turns=0;
unsigned fallbackLeg=0;
void FallbackWaypoint(unsigned width,unsigned height){
    // A closed city circuit when a map has no usable road count.
    static constexpr double points[8][2]={
        {.22,.30},{.50,.19},{.78,.30},{.82,.52},
        {.76,.74},{.50,.82},{.24,.74},{.18,.52}};
    const double targetX=width*points[fallbackLeg%8][0];
    const double targetZ=height*points[fallbackLeg%8][1];
    headingX=(targetX>cx+1)?1:(targetX<cx-1)?-1:0;
    headingZ=(targetZ>cz+1)?1:(targetZ<cz-1)?-1:0;
    waypointX=targetX;waypointZ=targetZ;
}
// sc3kre 2026-11-06: cISC3ZoneLayer::GetRoadCount (SIMRCI 0x100331a1) counts the road occupants of the one-cell strip
// BESIDE a straight row or column segment and returns 0 when begin and end differ on both x and z, so the old square
// query was always 0 (ROAD_COUNT_EMPTY on every city). Count road cells (geometry flag 0x8000) one by one instead.
bool IsRoad(cISC3OccupantManager* om,int x,int z){
    cISC3Occupant* o=nullptr;
    const bool road=om->GetOccupantAtCell(uint32_t(x),uint32_t(z),&o) && o && o->IsGeomFlag(0x8000);
    if(o)o->Release();
    return road;
}
uint32_t Roads(cISC3City* city,int x,int z,int radius){
    if(!city)return 0;
    cISC3OccupantManager* om=city->SurfaceOccupantManager();
    if(!om)return 0;
    const int w=int(city->CellCountX()),h=int(city->CellCountZ());
    if(x<radius || z<radius || x+radius>=w || z+radius>=h)return 0;
    uint32_t n=0;
    for(int i=x-radius;i<=x+radius;++i)for(int j=z-radius;j<=z+radius;++j)n+=IsRoad(om,i,j);
    return n;
}
// sc3kre 2026-11-06 (owner: patrol tied to police / military): the patrol visits the military base and every police
// station in turn along the roads. Type ids from CitySim.ini: 11002 Military Base, 13130 PoliceStation,
// 13120 SmallPoliceStation. Found by a cell scan once per patrol start (a station answers on each of its cells,
// so hits closer than 4 cells to a kept one are the same building).
struct Post{int x,z;uint32_t type;};
std::vector<Post> posts;
size_t postIndex=0;
bool postsScanned=false;
void ScanPosts(cISC3City* city){
    posts.clear();postIndex=0;postsScanned=true;
    cISC3OccupantManager* om=city?city->SurfaceOccupantManager():nullptr;
    if(!om)return;
    const int w=int(city->CellCountX()),h=int(city->CellCountZ());
    int bases=0,police=0;
    for(int x=0;x<w;++x)for(int z=0;z<h;++z){
        cISC3Occupant* o=nullptr;
        if(!om->GetOccupantAtCell(uint32_t(x),uint32_t(z),&o) || !o)continue;
        const uint32_t t=o->TypeId();
        o->Release();
        if(t!=11002 && t!=13130 && t!=13120)continue;
        bool seen=false;
        const int sameLot=t==11002?12:4;   // the base is a large plopped lot (measured: 9 hits at 4)
        for(const Post& p:posts)if(p.type==t && std::abs(p.x-x)<sameLot && std::abs(p.z-z)<sameLot){seen=true;break;}
        if(seen)continue;
        if(t==11002){posts.insert(posts.begin(),Post{x,z,t});++bases;}else{posts.push_back(Post{x,z,t});++police;}
    }
    char b[96];wsprintfA(b,"PATROL_POSTS military %d police %d",bases,police);Log(b);
    for(const Post& p:posts){wsprintfA(b,"PATROL_POST (%d,%d) type %u",p.x,p.z,p.type);Log(b);}
}
void SelectWaypoint(cISC3City* city,unsigned width,unsigned height){
    if(!patrolReady){
        double best=-1;int bestX=0,bestZ=0;
        for(int x=int(width*.12);x<int(width*.85);x+=std::max(4,int(width/14)))
            for(int z=int(height*.24);z<int(height*.80);z+=std::max(4,int(height/14))){
                const double rx=(patrolMode && !posts.empty())?posts[postIndex].x:width*.17;
                const double rz=(patrolMode && !posts.empty())?posts[postIndex].z:height*.60;
                const double score=double(Roads(city,x,z,2))-.04*std::hypot(x-rx,z-rz);
                if(score>best){best=score;bestX=x;bestZ=z;}
            }
        patrolReady=best>0;
        if(!patrolReady){Log("ROAD_COUNT_EMPTY: city circuit fallback");return;}
        waypointX=bestX;waypointZ=bestZ;headingX=1;headingZ=0;
        Log("ROAD_PATROL_FOUND");
        return;
    }
    const int x=int(std::round(cx)),z=int(std::round(cz));
    const int step=std::max(3,int(std::min(width,height)/28));
    const int dirX[4]={headingX,-headingZ,headingZ,-headingX};
    const int dirZ[4]={headingZ,headingX,-headingX,-headingZ};
    double best=-1e9;int choice=0;
    for(int i=0;i<4;++i){
        const int tx=x+dirX[i]*step,tz=z+dirZ[i]*step;
        const double road=double(Roads(city,tx,tz,2));
        if(!road)continue;
        double score=road+(i==0?5.:i==3?-10.:((turns+i)%3==0?1.5:0.));
        if(patrolMode && !posts.empty()){   // sc3kre: head for the current post
            const Post& p=posts[postIndex];
            const double gain=std::hypot(x-p.x,z-p.z)-std::hypot(tx-p.x,tz-p.z);
            score+=gain*2.;
        }
        if(score>best){best=score;choice=i;}
    }
    if(best<-1e8){
        // Stay in the city and backtrack rather than jumping to the fallback route.
        headingX=-headingX;headingZ=-headingZ;
        waypointX=std::clamp(double(x+headingX*step),3.,double(city->CellCountX())-4.);
        waypointZ=std::clamp(double(z+headingZ*step),3.,double(city->CellCountZ())-4.);
        Log("ROAD_PATROL_BACKTRACK");return;
    }
    if(patrolMode && !posts.empty()){
        // reached = within 16 cells (a post can sit far from its nearest road: the Craterville base is ~30 cells off
        // the road net). Stuck = no new best distance for 25 s: go on to the next post.
        static double bestDist=1e9;static ULONGLONG bestAt=0;static size_t bestFor=size_t(-1);
        const ULONGLONG t=GetTickCount64();
        const double d=std::hypot(x-posts[postIndex].x,z-posts[postIndex].z);
        if(bestFor!=postIndex){bestFor=postIndex;bestDist=d;bestAt=t;}
        if(d<bestDist-1.){bestDist=d;bestAt=t;}
        const bool reached=d<16.,stuck=t-bestAt>25000;
        if(reached || stuck){
            char b[96];wsprintfA(b,"PATROL_POST_%s %u (%d,%d) type %u dist %d",reached?"REACHED":"SKIPPED",unsigned(postIndex),
                posts[postIndex].x,posts[postIndex].z,posts[postIndex].type,int(d));
            Log(b);postIndex=(postIndex+1)%posts.size();bestFor=size_t(-1);
        }
    }
    headingX=dirX[choice];headingZ=dirZ[choice];
    waypointX=x+headingX*step;waypointZ=z+headingZ*step;
    if(choice==1)Log("ROAD_TURN_LEFT");
    else if(choice==2)Log("ROAD_TURN_RIGHT");
    else if(turns%10==0)Log("ROAD_GO_STRAIGHT");
    ++turns;
}
void Direction(int key,unsigned rotation,double& dx,double& dz){
    static constexpr int leftX[4]={1,-1,-1,1},leftZ[4]={-1,-1,1,1};
    static constexpr int upX[4]={-1,-1,1,1},upZ[4]={-1,1,1,-1};
    rotation&=3;
    if(key=='A' || key==VK_LEFT){dx+=leftX[rotation];dz+=leftZ[rotation];}
    if(key=='D' || key==VK_RIGHT){dx-=leftX[rotation];dz-=leftZ[rotation];}
    if(key=='W' || key==VK_UP){dx+=upX[rotation];dz+=upZ[rotation];}
    if(key=='S' || key==VK_DOWN){dx-=upX[rotation];dz-=upZ[rotation];}
}
bool ConfigureBlend(void* sprite,uint8_t alpha){
    HMODULE mod=GetModuleHandleA("SIMSPR.DLL");
    if(!At(sprite,10,mod,0x5ADF5) || !At(sprite,15,mod,0x15B0B) ||
       !At(sprite,16,mod,0x5AE16))return false;
    static constexpr uint8_t setter[]={0x8b,0x41,0x04,0x8b,0xd0,0x33,0x54,0x24,0x04,
        0x81,0xe2,0xff,0xff,0x01,0x00,0x33,0xd0,0xb0,0x01,0x89,0x51,0x04,0xc2,0x04,0x00};
    if(std::memcmp(reinterpret_cast<const uint8_t*>(mod)+0x5ADF5,setter,sizeof(setter)))return false;
    using Set=bool(__thiscall*)(void*,uint32_t);
    const uint32_t flags=alpha==255?0u:(0x10000u|alpha);
    return V<Set>(sprite,10)(sprite,flags);
}

void StopTimer(){if(timer){KillTimer(nullptr,timer);timer=0;}}
void Unpin(){
    for(unsigned z=0;z<5;++z)for(unsigned i=0;i<attributeCount;++i)if(pinned[z][i] && attributes[i]){
        using Fn=uint32_t(__thiscall*)(void*,uint16_t);
        auto fn=V<Fn>(attributes[i],14);
        if(fn)fn(attributes[i],uint16_t(z*4));
        pinned[z][i]=false;
    }
}
void ReleaseAssets(){
    Unpin();
    for(void*& attr:attributes){Release(attr);attr=nullptr;}
    if(segment){
        if(registered && resourceManager){
            using Fn=bool(__thiscall*)(void*,void*);
            auto unreg=V<Fn>(resourceManager,26);
            if(!unreg || !unreg(resourceManager,segment))return; // retain failed ownership
            registered=false;
        }
        using Fn=bool(__thiscall*)(void*);
        auto shutdown=V<Fn>(segment,4);
        if(shutdown)shutdown(segment);
        Release(segment);segment=nullptr;resourceManager=nullptr;
    }
}
bool RemoveSprites(void* current){
    const bool same=current && current==spriteMap;
    using Fn=bool(__thiscall*)(void*,void*,int32_t,int32_t,bool);
    auto remove=same?V<Fn>(current,65):nullptr;
    bool clean=true;
    for(auto& rec:sprites)if(rec.ptr){
        if(same && (!remove || !remove(current,rec.ptr,rec.x,rec.z,true))){clean=false;continue;}
        Release(rec.ptr);rec={};
    }
    if(clean)spriteMap=nullptr;
    return clean;
}
bool Stop(void* current){
    playing=false;StopTimer();
    if(!RemoveSprites(current)){blocked=true;Log("CLEANUP_FAILED: restart game");return false;}
    Log("STOP_OK");
    return true;
}
bool OpenAssets(cISC3App* app,cIGZCOM* com,const std::string& path){
    if(attributes[0])return true;
    if(!app || !com)return false;
    for(const char* ext:{".IXF",".DAT",".SII"}){
        std::string filename=path.substr(0,path.size()-4)+ext;
        DWORD flags=GetFileAttributesA(filename.c_str());
        if(flags==INVALID_FILE_ATTRIBUTES || flags&FILE_ATTRIBUTE_DIRECTORY)return false;
    }
    void* candidate=nullptr;
    if(!com->GetClassObject(indexedSegment,segmentIID,&candidate) || !candidate)return false;
    HMODULE res=GetModuleHandleA("GZResourceD.dll");
    void* manager=static_cast<void*>(app->GetResourceManager());
    if(!At(candidate,3,res,0xCA78) || !At(candidate,4,res,0xD0A1) ||
       !At(candidate,18,res,0xD2FC) || !At(manager,5,res,0x12C48) ||
       !At(manager,23,res,0x1229F) || !At(manager,26,res,0x12333)){
        Release(candidate);return false;
    }
    using Init=bool(__thiscall*)(void*,uint32_t,const cIGZString*,bool);
    cRZBaseString filename(path.c_str());
    auto init=V<Init>(candidate,3);
    if(!init || !init(candidate,group,&filename,true)){Release(candidate);return false;}
    using Test=bool(__thiscall*)(void*,const Key*);
    auto test=V<Test>(candidate,18);
    bool good=test!=nullptr;
    for(unsigned i=0;i<attributeCount && good;++i){Key key{attrType,group,attrBase+i};good=test(candidate,&key);}
    using Shutdown=bool(__thiscall*)(void*);
    if(!good){V<Shutdown>(candidate,4)(candidate);Release(candidate);return false;}
    using Register=bool(__thiscall*)(void*,void*);
    auto reg=V<Register>(manager,23);
    if(!reg || !reg(manager,candidate)){V<Shutdown>(candidate,4)(candidate);Release(candidate);return false;}
    segment=candidate;resourceManager=manager;registered=true;
    using Get=bool(__thiscall*)(void*,const Key*,uint32_t,void**);
    auto get=V<Get>(manager,5);
    for(unsigned i=0;i<attributeCount;++i){
        Key key{attrType,group,attrBase+i};
        if(!get(manager,&key,attrIID,&attributes[i]) || !attributes[i])return false;
    }
    return true;
}
bool PinZoom(unsigned zoom){
    if(zoom>4)return false;
    HMODULE spr=GetModuleHandleA("SIMSPR.DLL");
    for(unsigned i=0;i<attributeCount;++i){
        if(pinned[zoom][i])continue;
        if(!attributes[i] || !At(attributes[i],13,spr,0x1592) || !At(attributes[i],14,spr,0x15C4))return false;
        using Fn=bool(__thiscall*)(void*,uint16_t);
        auto load=V<Fn>(attributes[i],13);
        if(!load(attributes[i],uint16_t(zoom*4)))return false;
        pinned[zoom][i]=true;
    }
    return true;
}
bool Paint(cISC3App* app){
    auto* city=app?app->GetCity():nullptr;
    void* map=Map(app);
    if(!city || !map || !ValidMap(map) || !attributes[0])return false;
    if(cityIdentity!=city || (spriteMap && spriteMap!=map))return false;
    const unsigned width=city->CellCountX(),height=city->CellCountZ();
    // sc3kre 2026-11-06: up to 1024 for sc3bigcity (was 256; nothing else here depends on it)
    if(width<16 || height<16 || width>1024 || height>1024){Log("PAINT_SIZE_REJECTED");return false;}
    const auto* bytes=static_cast<const uint8_t*>(map);
    int altitudeShift=0,tileShift=0,horizontalShift=0;
    unsigned rotation=0;
    std::memcpy(&altitudeShift,bytes+0x44,4);
    std::memcpy(&tileShift,bytes+0x4c,4);
    std::memcpy(&horizontalShift,bytes+0x48,4);
    std::memcpy(&rotation,bytes+0x2c,4);
    if(altitudeShift<0 || altitudeShift>4 || tileShift<0 || tileShift>8 ||
       horizontalShift<0 || horizontalShift>8 || rotation>3 || !PinZoom(unsigned(altitudeShift))){
        char b[96];wsprintfA(b,"PAINT_VIEW_REJECTED alt %d tile %d hor %d rot %u",altitudeShift,tileShift,horizontalShift,rotation);
        Log(b);return false;   // sc3kre: say why
    }
    const ULONGLONG now=GetTickCount64();
    const double dt=std::clamp(double(now-lastTick)/1000.,0.,.10);
    lastTick=now;
    // The road query runs at waypoints; rendering still just interpolates.
    travel=std::clamp(double(now-startTime)/180000.,0.,1.);
    const double pathX=width*(.15+.70*travel+.012*std::sin(6.2831853*travel));
    const double pathZ=height*(.61-.22*travel+.009*std::sin(6.2831853*travel));
    if(patrolMode && !postsScanned)ScanPosts(city);
    if(!pilotMode && !returning && now>=nextWaypoint &&
       (!patrolReady || std::hypot(waypointX-cx,waypointZ-cz)<.4)){
        if(cx==0 && cz==0){cx=pathX;cz=pathZ;}
        SelectWaypoint(city,width,height);
        nextWaypoint=now+(patrolReady?200:7000);
    }
    if(patrolMode && !pilotMode && !returning && !patrolReady){
        if((waypointX==0 && waypointZ==0) ||
           std::hypot(waypointX-cx,waypointZ-cz)<1.0){
            if(waypointX!=0 || waypointZ!=0)fallbackLeg=(fallbackLeg+1)%8;
            FallbackWaypoint(width,height);
        }
    }
    if(!motionReady){
        aircraft[0].position={cx,cz};
        formationAngle=std::atan2(waypointZ-cz,waypointX-cx);
        const double bx=-std::cos(formationAngle),bz=-std::sin(formationAngle);
        aircraft[1].position={cx+bx*4.-bz*3.,cz+bz*4.+bx*3.};
        aircraft[2].position={cx+bx*4.+bz*3.,cz+bz*4.-bx*3.};
        for(unsigned i=0;i<3;++i){
            auto& pos=aircraft[i].position;
            pos.x=std::clamp(pos.x,3.,double(width)-4.);
            pos.z=std::clamp(pos.z,3.,double(height)-4.);
            int32_t ground=0;
            if(!Ground(map,int(pos.x),int(pos.z),width,height,ground))return false;
            aircraftAltitude[i]=ground+12*256;
        }
        aircraftYaw.fill(formationAngle);manualYaw=formationAngle;
        motionReady=true;
    }
    flight::Vec desired{};
    double cruise=1.15;
    if(pilotMode){
        double dx=0,dz=0;
        DWORD pid=0;GetWindowThreadProcessId(GetForegroundWindow(),&pid);
        const bool focused=pid==GetCurrentProcessId();
        const bool leftTurn=focused && (GetAsyncKeyState(VK_OEM_4)&0x8000);
        const bool rightTurn=focused && (GetAsyncKeyState(VK_OEM_6)&0x8000);
        if(leftTurn && !turnLeftHeld){manualYaw=aircraftYaw[0]+.7853981633974483;headingLocked=true;}
        if(rightTurn && !turnRightHeld){manualYaw=aircraftYaw[0]-.7853981633974483;headingLocked=true;}
        turnLeftHeld=leftTurn;turnRightHeld=rightTurn;
        if(focused)for(const int key:std::array<int,4>{'W','A','S','D'})
            if(GetAsyncKeyState(key)&0x8000)Direction(key,rotation,dx,dz);
        cruise=1.45;
        if(std::hypot(dx,dz)>.01){
            desired=flight::limited({dx,dz},1.)*cruise;nudgeActive=false;headingLocked=false;
        }else if(nudgeActive){
            desired=flight::arrival(aircraft[0].position,{manualX,manualZ},cruise);
            if(flight::length(aircraft[0].position-flight::Vec{manualX,manualZ})<.06)nudgeActive=false;
        }
    }else{
        returning=false;nudgeActive=false;headingLocked=false;
        const flight::Vec goal=(patrolReady||patrolMode)?flight::Vec{waypointX,waypointZ}:flight::Vec{pathX,pathZ};
        desired=flight::arrival(aircraft[0].position,goal,cruise);
    }
    flight::advance(aircraft[0],desired,dt,cruise,1.1);
    aircraft[0].position.x=std::clamp(aircraft[0].position.x,3.,double(width)-4.);
    aircraft[0].position.z=std::clamp(aircraft[0].position.z,3.,double(height)-4.);
    cx=aircraft[0].position.x;cz=aircraft[0].position.z;
    if(!nudgeActive){manualX=cx;manualZ=cz;}
    if(flight::length(aircraft[0].velocity)>.12){
        formationAngle=flight::turnToward(formationAngle,
            std::atan2(aircraft[0].velocity.z,aircraft[0].velocity.x),dt);
    }

    {   static ULONGLONG nextPos=0;   // sc3kre: lead aircraft position in the log, for camera checks
        if(now>=nextPos){char b[64];wsprintfA(b,"POS %d %d of %u",int(cx),int(cz),width);Log(b);nextPos=now+5000;} }
    if(now>=nextDensityCheck){
        narrowFormation=patrolReady && Roads(city,int(cx),int(cz),5)>28;
        nextDensityCheck=now+1500;
    }
    formationSpread+=( (narrowFormation?1.2:3.)-formationSpread)*std::min(1.,dt*.65);
    const double bx=-std::cos(formationAngle),bz=-std::sin(formationAngle);
    for(unsigned i=1;i<3;++i){
        const double side=i==1?formationSpread:-formationSpread;
        const double back=4.+(narrowFormation && i==2?2.:0.);
        flight::Vec target{cx+bx*back-bz*side,cz+bz*back+bx*side};
        target.x=std::clamp(target.x,3.,double(width)-4.);
        target.z=std::clamp(target.z,3.,double(height)-4.);
        const flight::Vec follow=flight::arrival(aircraft[i].position,target,1.75);
        flight::advance(aircraft[i],follow,dt,1.75,1.25);
    }
    for(unsigned i=0;i<3;++i){
        int32_t ground=0;
        if(!Ground(map,int(aircraft[i].position.x),int(aircraft[i].position.z),width,height,ground))return false;
        const double target=ground+12*256.;
        aircraftAltitude[i]+=std::clamp(target-aircraftAltitude[i],-320.*dt,320.*dt);
    }
    for(unsigned i=0;i<3;++i){
        const auto velocity=aircraft[i].velocity;
        if(headingLocked || flight::length(velocity)>.16){
            const double target=headingLocked?manualYaw:std::atan2(velocity.z,velocity.x);
            aircraftYaw[i]=flight::turnYaw(aircraftYaw[i],target,dt);
        }
    }
    double rightX=0,rightZ=0,upX=0,upZ=0;
    Direction('D',rotation,rightX,rightZ);Direction('W',rotation,upX,upZ);
    using Add=bool(__thiscall*)(void*,void*,int32_t,int32_t,int32_t,bool,int32_t,uint32_t);
    using Move=bool(__thiscall*)(void*,void*,int32_t,int32_t,int32_t,int32_t,int32_t);
    auto add=V<Add>(map,64);auto move=V<Move>(map,67);
    if(!add || !move)return false;
    spriteMap=map;
    for(unsigned n=0;n<sprites.size();++n){
        const int pilot=n%3;
        const int kind=n/3;
        const double x=aircraft[pilot].position.x,z=aircraft[pilot].position.z;
        const int32_t mx=int32_t(std::lround(x*256.)),mz=int32_t(std::lround(z*256.));
        const bool shadow=kind>=32;
        int32_t altitude=int32_t(std::lround(aircraftAltitude[pilot]));
        if(shadow){
            if(!Ground(map,int(x),int(z),width,height,altitude))return false;
            altitude+=8; // Small ground clearance, independent of aircraft height.
        }
        const unsigned phase=((now-startTime)/75+pilot)%3;
        const int facing=flight::screenHeading(aircraftYaw[pilot],{rightX,rightZ},{upX,upZ});
        const uint8_t targetAlpha=shadow ? (kind==32?22:28) : kind<8 ?
            (kind==facing?255:0) : (kind==int(8+phase*8+facing)?112:0);
        auto& s=sprites[n];
        if(s.ptr){
            // A facing change while hovering still needs a native dirty-region
            // update. One micro-unit is subpixel at every zoom.
            const int32_t drawX=mx+(s.alpha!=targetAlpha?1:0);
            if((targetAlpha || s.alpha) && (s.x!=drawX || s.z!=mz || s.altitude!=altitude)){
                if(!move(map,s.ptr,s.x,s.z,drawX,mz,altitude))return false;
                s.x=drawX;s.z=mz;s.altitude=altitude;
            }
            if(s.alpha!=targetAlpha){if(!ConfigureBlend(s.ptr,targetAlpha))return false;s.alpha=targetAlpha;}
        }else if(targetAlpha){
            using Create=bool(__thiscall*)(void*,void**);
            auto create=V<Create>(attributes[kind],31);
            void* sprite=nullptr;
            if(!create || !create(attributes[kind],&sprite) || !sprite)return false;
            if(!ConfigureBlend(sprite,targetAlpha)){
                Release(sprite);return false;
            }
            // Native image selection follows the city's current camera
            // rotation; this test uses the source's four isometric banks.
            if(!add(map,sprite,mx,mz,altitude,true,shadow?0:(kind<8?2:3),0)){
                Release(sprite);return false;
            }
            s={sprite,mx,mz,altitude,targetAlpha};
        }
    }
    return true;
}
// ===== sc3kre 2026-11-06: the flyover as a Reunirse petition (owner: offered when the city has a military base, the
// base deal was accepted and crime is high; accept = "apache on", reject = nothing). Static read in verify/apache/RESULTS.md:
//  - queue: SIMADV FUN_100208ac(mgr, id, 0, 1, 0, 120), thiscall, not exported (the call Civic Deals makes)
//  - answer: SIMADV 0x1002096a PetitionerButtonPressed(mgr, id, button 1 accept / 2 reject); texts: 0x10021b7c
//    GetPetitionerStructureFromID(mgr, id, rec), record +0x10 name, +0x14 title, +0x18 message, +0x1c / +0x20 buttons,
//    +0x24 / +0x28 reactions (cIGZString*). Both are detoured at their prologue, so a second plugin that swaps the
//    manager's vtable (Civic Deals) still reaches them.
//  - base: BuildingLayer vt+0x60(0x2AFA) > 0. The base lot is placed only after the mayor accepts petition 0xCD, so
//    a base in the city means the deal was accepted.
//  - crime: CrimeLayer()->GetAverageValue() > 40 with population > 10000, the Public Safety advisor's "high crime"
//    (Advisor-PublicSafety.ini HIGH_CRIME_LEVEL=40, SIMADV 0x100145ef).
// Petition id 0xDB (free; SIMADV's stock switch routes it to a no-op case). Data: SYS.PAK PetitionerExtraInfo
// 0x000000DB=19,2 and the six Sc3StringsPetitioner*.IXF records, added by re/tools/apache_patch.py.
// MSVC note: this file is built with MSVC (build_msvc.cmd); MSVC lays overloaded virtuals out in a different order
// than GCC, which the SDK headers were written for, so overloaded methods (cIGZString::FromChar) are called by slot.
constexpr uint32_t petitionID=0xDB;
bool petitionOffered=false;
void* petitionDirector=nullptr;
using BtnFn=bool(__thiscall*)(void*,uint32_t,uint32_t);
using InfoFn=bool(__thiscall*)(void*,uint32_t,void*);
BtnFn origButton=nullptr;InfoFn origInfo=nullptr;
bool Spanish(){
    using LangFn=const char*(__stdcall*)();
    HMODULE m=GetModuleHandleA("sc3mods.dll");
    auto f=m?reinterpret_cast<LangFn>(GetProcAddress(m,"sc3mods_lang")):nullptr;
    const char* c=f?f():nullptr;
    return c && c[0]=='e' && c[1]=='s';
}
const char* PetitionText(int i){
    static const char* es[7]={"Coronel Vidal, base militar","Operaci\xf3n Cielo Seguro",
        "Alcalde, la delincuencia no deja de subir. La base puede prestarle tres helic\xf3pteros Apache para patrullar la "
        "ciudad durante unos minutos. No cuesta nada a las arcas, aunque el ruido no le va a gustar a todo el mundo.",
        "Autorizar la patrulla","Rechazar la oferta",
        "Los helic\xf3pteros despegan ahora, Alcalde. Vigilaremos la ciudad desde el aire.",
        "Entendido, Alcalde. La base sigue a su disposici\xf3n si cambia de idea."};
    static const char* en[7]={"Colonel Vidal, military base","Operation Safe Skies",
        "Mayor, crime keeps rising. The base can lend you three Apache helicopters to patrol the city for a few minutes. "
        "It costs the treasury nothing, though not everyone will like the noise.",
        "Authorize the patrol","Decline the offer",
        "The helicopters are taking off now, Mayor. We will watch the city from the air.",
        "Understood, Mayor. The base remains at your service if you change your mind."};
    return (Spanish()?es:en)[i];
}
bool __fastcall HookInfo(void* mgr,void*,uint32_t id,void* rec){
    const bool r=origInfo(mgr,id,rec);
    if(id==petitionID && rec && !IsBadReadPtr(rec,0x2c)){
        for(int i=0;i<7;++i){
            void* str=*reinterpret_cast<void**>(static_cast<uint8_t*>(rec)+0x10+4*i);
            if(!str || IsBadReadPtr(str,4))continue;
            using FromChar=uint32_t(__thiscall*)(void*,const char*);
            (*reinterpret_cast<FromChar**>(str))[0x10/4](str,PetitionText(i));
        }
    }
    return r;
}
void StartFromPetition();
bool __fastcall HookButton(void* mgr,void*,uint32_t id,uint32_t button){
    const bool r=origButton(mgr,id,button);
    if(id==petitionID){Log(button==1?"PETITION_ACCEPTED":"PETITION_REJECTED");if(button==1)StartFromPetition();}
    return r;
}
bool Detour(uint8_t* fn,const uint8_t* expect,int len,void* hook,void** tramp){
    if(std::memcmp(fn,expect,len))return false;
    auto* t=static_cast<uint8_t*>(VirtualAlloc(nullptr,32,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    if(!t)return false;
    std::memcpy(t,fn,len);t[len]=0xE9;*reinterpret_cast<int32_t*>(t+len+1)=int32_t((fn+len)-(t+len+5));
    DWORD old;if(!VirtualProtect(fn,len,PAGE_EXECUTE_READWRITE,&old))return false;
    *tramp=t;fn[0]=0xE9;*reinterpret_cast<int32_t*>(fn+1)=int32_t(static_cast<uint8_t*>(hook)-(fn+5));
    for(int i=5;i<len;++i)fn[i]=0x90;
    FlushInstructionCache(GetCurrentProcess(),fn,len);
    return true;
}
bool InstallPetition(){
    static int state=0;   // 0 not tried, 1 in, -1 refused
    if(state)return state>0;
    auto* b=reinterpret_cast<uint8_t*>(GetModuleHandleA("SIMADV.DLL"));
    if(!b)return false;
    static const uint8_t eBtn[7]={0x55,0x8b,0xec,0x53,0x8b,0x5d,0x08},eInfo[5]={0x8b,0x49,0x28,0x85,0xc9};
    state=-1;
    if(*reinterpret_cast<uint32_t*>(b+0x208b6)!=0x7d8b5756 || b[0x208ba]!=0x08){Log("PETITION_OFF: SIMADV queue differs");return false;}
    if(!Detour(b+0x2096a,eBtn,7,reinterpret_cast<void*>(&HookButton),reinterpret_cast<void**>(&origButton)) ||
       !Detour(b+0x21b7c,eInfo,5,reinterpret_cast<void*>(&HookInfo),reinterpret_cast<void**>(&origInfo))){
        Log("PETITION_OFF: SIMADV petitioner functions differ");return false;}
    state=1;Log("PETITION_HOOKS_IN");return true;
}
void CALLBACK OfferTick(HWND,UINT,UINT_PTR,DWORD){
    if(petitionOffered || !cityReady || playing)return;
    cRZAutoRefCount<cISC3App> app;
    if(!App(framework,app))return;
    cISC3City* city=app->GetCity();
    if(!city || !InstallPetition())return;
    auto* bl=city->BuildingLayer();auto* cr=city->CrimeLayer();auto* res=city->ResidentialLayer();
    if(!bl || !cr || !res)return;
    using Track=uint32_t(__thiscall*)(void*,uint32_t);   // SDK says bool; the body returns the count (SIMGEOM 0x10003d85)
    const uint32_t bases=(*reinterpret_cast<Track**>(bl))[0x60/4](bl,0x2AFA);
    const unsigned crime=cr->GetAverageValue();const int pop=res->GetPopulation();
    static ULONGLONG nextLog=0;const ULONGLONG now=GetTickCount64();
    if(now>=nextLog){char b[96];wsprintfA(b,"PETITION_CHECK base %d crime %u pop %d",int(bases),crime,pop);Log(b);nextLog=now+60000;}
    const bool force=GetEnvironmentVariableA("APACHE_PETITION_FORCE",nullptr,0)>0;   // lab: offer without the conditions
    if(!force && (bases==0 || bases==0xFFFFFFFFu || crime<=40 || pop<=10000))return;
    void* mgr=city->GetPetitionerManager();
    auto* b=reinterpret_cast<uint8_t*>(GetModuleHandleA("SIMADV.DLL"));
    if(!mgr || !b)return;
    using AddFn=bool(__thiscall*)(void*,uint32_t,int,uint8_t,uint8_t,uint8_t);
    petitionOffered=true;   // once per game session either way: SIMADV keeps offered ids until exit
    const bool ok=reinterpret_cast<AddFn>(b+0x208ac)(mgr,petitionID,0,1,0,120);
    Log(ok?"PETITION_QUEUED":"PETITION_QUEUE_REFUSED");
}

void CALLBACK Tick(HWND,UINT,UINT_PTR id,DWORD){
    if(id!=timer || !playing || blocked)return;
    const ULONGLONG now=GetTickCount64();
    cRZAutoRefCount<cISC3App> app;
    if(!App(framework,app) || !app->GetCity() || !Map(app))return;
    if(!patrolMode && now-startTime>=180000){Stop(Map(app));Ticker(app,"MILITARY EXERCISE CONCLUDES; PIGEONS RETURN TO NORMAL DUTIES.");return;}
    if(now>=nextTicker){
        static constexpr const char* messages[]={
            "MILITARY EXERCISE OVER CITY; MAYOR CLAIMS TO HAVE BEEN INFORMED.",
            "DID THE MAYOR APPROVE THIS? CITY HALL CHECKING PAPERWORK.",
            "HELICOPTER FORMATION DRAWS CROWDS, COMPLAINTS, AND BINOCULARS.",
            "LOW-FLYING HELICOPTERS GIVE LOCAL PIGEONS RIGHT-OF-WAY CONCERNS.",
            "LOCAL PIGEONS DEMAND ADVANCE NOTICE OF FUTURE FLYOVERS."};
        Ticker(app,patrolMode?"MILITARY HELICOPTERS CONTINUE CITY PATROL; MAYOR REQUESTS A FLIGHT PLAN.":
            messages[((now-startTime)/26000)%5]);nextTicker=now+(patrolMode?85000:26000);
    }
    if(now<nextDraw)return;
    nextDraw=now+25;
    if(!Paint(app)){StopTimer();blocked=true;playing=false;}
    if(blocked)Log("DRAW_FAILED: restart game");
}
}

class ApacheDirector final:public cRZMessageCOMDirector {
    cIGZCOM* com=nullptr;
    std::string assetPath;
public:
    uint32_t GetDirectorID()const override{return directorID;}
    bool OnStart(cIGZCOM* value)override{com=value;petitionDirector=this;auto* f=com?com->FrameWork():nullptr;if(!f)return false;f->AddHook(this);return true;}
    bool PostAppInit()override{
        cRZAutoRefCount<cISC3App> app;
        if(!App(mpFrameWork,app))return false;
        auto* manager=app->GetCheatCodeManager();if(!manager)return false;
        manager->RegisterCheatCode(onID,cRZBaseString("apache on"));manager->AddNotification(this,onID);
        manager->RegisterCheatCode(offID,cRZBaseString("apache off"));manager->AddNotification(this,offID);
        manager->RegisterCheatCode(patrolID,cRZBaseString("apache patrol"));manager->AddNotification(this,patrolID);
        const std::array<std::pair<uint32_t,const char*>,7> controls={{{pilotID,"apache pilot"},
            {autoID,"apache auto"},{upID,"apache up"},{downID,"apache down"},
            {leftID,"apache left"},{rightID,"apache right"},{turnID,"apache turn"}}};
        for(const auto& c:controls){manager->RegisterCheatCode(c.first,cRZBaseString(c.second));manager->AddNotification(this,c.first);}
        cIGZMessageServerPtr messages;
        if(messages){messages->AddNotification(this,preCity);messages->AddNotification(this,postCity);}
        SetTimer(nullptr,0,15000,OfferTick);   // sc3kre: Reunirse petition check
        cRZBaseString module;ModulePath(module);
        assetPath=module.ToChar();
        size_t slash=assetPath.find_last_of("\\/");
        if(slash!=std::string::npos)assetPath.resize(slash+1);
        logPath=assetPath+"SC3KUApacheFlyover.log";
        assetPath+="Res\\Sprites\\SC3KU_ApacheFlyover.IXF";
        Log("INIT");
        framework=mpFrameWork;cityReady=Map(app)!=nullptr;
        return true;
    }
    bool PreAppShutdown()override{
        cRZAutoRefCount<cISC3App> app;App(mpFrameWork,app);
        Stop(app && app->GetCity()==cityIdentity?Map(app):nullptr);
        if(!blocked)ReleaseAssets();
        return true;
    }
    bool AbortiveQuit()override{return PreAppShutdown();}
    bool DoMessage(cGZMessage& message)override{
        if(message.dwMessageType==preCity){
            cRZAutoRefCount<cISC3App> app;App(mpFrameWork,app);
            Stop(app && app->GetCity()==cityIdentity?Map(app):nullptr);
            if(!blocked)ReleaseAssets();
            pilotMode=returning=patrolMode=false;cityIdentity=nullptr;cityReady=false;return true;
        }
        if(message.dwMessageType==postCity){cityReady=true;return true;}
        if(message.dwMessageType!=cheatMessage)return true;
        const uint32_t command=message.dwData1;
        if(command<onID || command>turnID)return true;
        cRZAutoRefCount<cISC3App> app;
        if(!App(mpFrameWork,app))return true;
        void* current=app->GetCity()==cityIdentity?Map(app):nullptr;
        if(command==offID){pilotMode=returning=patrolMode=false;Stop(current);return true;}
        if(command!=onID && command!=patrolID){
            if(!playing || blocked || !app->GetCity() || !current || !ValidMap(current))return true;
            if(command==autoID){pilotMode=false;returning=false;headingLocked=false;Log("AUTO");return true;}
            if(!pilotMode){
                manualX=cx>=2?cx:app->GetCity()->CellCountX()*.15;
                manualZ=cz>=2?cz:app->GetCity()->CellCountZ()*.61;
                pilotMode=true;returning=false;headingLocked=false;nudgeActive=false;
            }
            if(command==turnID){manualYaw=aircraftYaw[0]+3.141592653589793;headingLocked=true;Log("PILOT_TURN");return true;}
            if(command==pilotID)headingLocked=false;
            if(command!=pilotID){
                unsigned rotation=0;
                std::memcpy(&rotation,static_cast<const uint8_t*>(current)+0x2c,4);
                if(rotation>3)return true;
                const int key=command==upID?VK_UP:command==downID?VK_DOWN:
                    command==leftID?VK_LEFT:VK_RIGHT;
                double dx=0,dz=0;Direction(key,rotation,dx,dz);
                manualX+=dx*2.8;manualZ+=dz*2.8;
                manualX=std::clamp(manualX,3.,double(app->GetCity()->CellCountX())-4.);
                manualZ=std::clamp(manualZ,3.,double(app->GetCity()->CellCountZ())-4.);
                nudgeActive=true;headingLocked=false;
            }
            Log("PILOT_COMMAND");return true;
        }
        if(blocked || !cityReady || !app->GetCity() || !Map(app) || !ValidMap(Map(app))){Log("START_BLOCKED: city or SIMSPR unavailable");return true;}
        if(command==patrolID && playing){
            patrolMode=true;pilotMode=false;returning=false;postsScanned=false;
            nextWaypoint=GetTickCount64();nextTicker=0;
            Log("PATROL_CONTINUOUS");return true;
        }
        if(playing && !Stop(current))return true;
        if(!OpenAssets(app,com,assetPath)){Log("ASSETS_FAILED: check Apps/Res/Sprites");ReleaseAssets();return true;}
        cityIdentity=app->GetCity();
        startTime=lastTick=GetTickCount64();nextTicker=nextDraw=nextWaypoint=nextDensityCheck=0;
        pilotMode=returning=turnLeftHeld=turnRightHeld=false;manualX=manualZ=0;
        motionReady=nudgeActive=headingLocked=false;aircraft={};aircraftAltitude={};
        formationAngle=0;formationSpread=3.;facingCandidate=-1;facingSince=0;
        patrolMode=command==patrolID;postsScanned=false;
        patrolReady=narrowFormation=false;turns=fallbackLeg=0;
        travel=0;cx=cz=0;playing=true;
        timer=SetTimer(nullptr,0,20,Tick);
        if(!timer){playing=false;Log("TIMER_FAILED");return true;}
        Log(patrolMode?"PATROL_START_CONTINUOUS":"START_TIMED");
        return true;
    }
};
namespace{void StartFromPetition(){   // sc3kre: accept = the same path as the cheat "apache on"
    if(!petitionDirector)return;
    cGZMessage m(cheatMessage);m.dwData1=onID;
    static_cast<ApacheDirector*>(petitionDirector)->DoMessage(m);
}}
cRZCOMDllDirector* RZGetCOMDllDirector(){static ApacheDirector director;return &director;}
