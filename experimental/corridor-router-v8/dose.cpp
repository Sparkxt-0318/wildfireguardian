#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
#include <cstdlib>
// Coordinates and bounds are integers. Reject inadmissible dimensions before multiplying.
using I = int64_t;
static I ceilroot(I q){
    I r=static_cast<I>(std::sqrt(static_cast<double>(q)));
    while(r*r<q) ++r;
    while(r>0 && (r-1)*(r-1)>=q) --r;
    return r;
}
extern "C" int coefficients(int ne, int ns, const I* receivers,const I* sources, I side,I h,I density,I* out){
    if(side<1 || side>2000 || h<=0 || h>2000 || density<0 || (__int128)density*795774715*h*side*side>INT64_MAX*(__int128)10000000000) return -1;
    for(int i=0;i<ne;i++) for(int j=0;j<ns;j++){
        const I* a=receivers+4*i; const I* b=sources+2*j;
        I gap=std::max({I(0),a[0]-(b[0]+side),b[0]-a[1],a[2]-(b[1]+side),b[1]-a[3]});
        int n=(gap<600 && side%25==0)?25:(gap<2400 && side%5==0)?5:(side%3==0 && gap<6000)?3:1;
        I w=side/n; __int128 numerator=(__int128)density*795774715*h*w*w;
        I total=0;
        for(int ix=0;ix<n;ix++) for(int iy=0;iy<n;iy++){
            I x=b[0]+ix*w,y=b[1]+iy*w;
            I dx=std::max(std::abs(a[0]-x-w),std::abs(a[1]-x));
            I dy=std::max(std::abs(a[2]-y-w),std::abs(a[3]-y));
            if(dx>200000 || dy>200000)return -1;
            I r=ceilroot(dx*dx+dy*dy+h*h);
            total+=(I)(numerator/((__int128)10000000000*r*r*r));
        }
        out[i*ns+j]=total;
    }
    return 0;
}
// Clock-ordered shortest dose in an optimistic original-node graph. Each edge uses
// the guaranteed active sources in each clock bin. The final action is a required stay.
extern "C" int64_t mincost(int nn,int ne,int dep,int last,int start,int dest,int dwell,int step,int bins,
    const int* first,const int* to,const int* duration,const int* remaining,const int* at_goal,
    const I* rate,const I* prefix,const int* off,const int* starts,const int* ends,I budget,int64_t* counter,int* first_tick, int ng,const int* birth,const int* end,const I* base,const I* mean){
    constexpr I INF=INT64_C(1)<<60;
    if((I)(last-dep+1)*nn>100000000 || last<dep || budget<0 || budget>=INF/2)return -2;
    std::vector<I> d((I)(last-dep+1)*nn,INF);d[start]=0;
    auto integ=[&](int e,int t){int k=t/step;return prefix[(I)e*bins+k]+(t%step)*rate[(I)e*bins+k];};
    auto costof=[&](int e,int t,int b){
        I v=integ(e,b)-integ(e,t),out=0;
        for(int j=0;j<ng;j++){
            I full=std::max(I(0),std::min<I>(b,end[j])-std::max<I>(t,birth[j]));
            out+=full*((full==b-t?mean:base)[(I)e*ng+j]);
        }
        return std::max(v,out);
    };
    I minimum=INF,visited=0;
    for(int t=dep;t<=last;t++){
        I* now=d.data()+(I)(t-dep)*nn;
        if(at_goal[t] && now[dest]<=budget){
            I c=now[dest]+costof(ne,t,t+dwell);minimum=std::min(minimum,c);
            if(c<=budget && *first_tick<0)*first_tick=t;
        }
        for(int u=0;u<nn;u++){
            if(now[u]>budget || t+remaining[u]>last)continue;
            visited++;
            for(int e=first[u];e<first[u+1];e++){
                int v=to[e],b=t+duration[e];
                if(b+remaining[v]>last)continue;
                bool banned=false; for(int i=off[e];i<off[e+1];i++) if(starts[i]<=t && t<ends[i]){banned=true;break;}
                if(banned)continue;
                I cost=now[u]+costof(e,t,b);
                if(cost<=budget){
                    I& val=d[(I)(b-dep)*nn+v];val=std::min(val,cost);
                }
            }
        }
    }
    *counter=visited;
    return minimum;
}

// Second-order midpoint inequality on a whole road and a source square. For
// f=h/r^3 the smallest Hessian eigenvalue is -3h/r^5. Averaging eliminates
// the linear term; the two independent coordinate variances sum to w^2/6
// for the tile and |v-u|^2/12 for a uniform road position.
using J=__int128_t;
extern "C" int mean_coeff(int ne,int ns,const I* lines,const I* sources,I side,I h,I density,I* out){
    if(side<1||side>2000||h<=0||h>2000||density<0||density>INT64_C(100000000000000))return -1;
    for(int i=0;i<ne;i++)for(int j=0;j<ns;j++){
        const I* v=lines+4*i;const I* s=sources+2*j;
        for(int k=0;k<4;k++)if(v[k]<0||v[k]>200000000)return -1;
        I gx=std::max({I(0),std::min(v[0],v[2])-s[0]-side,s[0]-std::max(v[0],v[2])-1});
        I gy=std::max({I(0),std::min(v[1],v[3])-s[1]-side,s[1]-std::max(v[1],v[3])-1});
        I gap=std::max(gx,gy),len=std::max(std::abs(v[0]-v[2]),std::abs(v[1]-v[3]));
        int P=std::clamp<int>(1+len/std::max<I>(20,gap/3),1,32);
        int n=(gap<140 && side%25==0)?25:(gap<800 && side%15==0)?15:(gap<2800 && side%5==0)?5:(gap<10000 && side%3==0)?3:1;
        I w=side/n,total=0;
        for(int k=0;k<P;k++){
            I ax=((P-k)*v[0]+k*v[2])/P, bx=((P-k-1)*v[0]+(k+1)*v[2])/P;
            I ay=((P-k)*v[1]+k*v[3])/P, by=((P-k-1)*v[1]+(k+1)*v[3])/P;
            I pad=P==1?1:2;
            I length2=(std::abs(ax-bx)+pad)*(std::abs(ax-bx)+pad)+(std::abs(ay-by)+pad)*(std::abs(ay-by)+pad);
            for(int ix=0;ix<n;ix++)for(int iy=0;iy<n;iy++){
                I x=s[0]+ix*w,y=s[1]+iy*w;
                I dx=std::max({I(0),std::min(ax,bx)-x-w,x-std::max(ax,bx)-pad});
                I dy=std::max({I(0),std::min(ay,by)-y-w,y-std::max(ay,by)-pad});
                I dx2=std::max(std::abs(2*x+w-ax-bx),std::abs(2*x+w-ax-bx-2*pad));
                I dy2=std::max(std::abs(2*y+w-ay-by),std::abs(2*y+w-ay-by-2*pad));
                if(dx2>400000||dy2>400000)return -1;
                I near2=dx*dx+dy*dy+h*h,r=ceilroot(near2);r-=r*r>near2;
                I r2=ceilroot(dx2*dx2+dy2*dy2+4*h*h);
                if(r>250000) return -1;
                J num=J(density)*795774715*h*w*w;
                J max_int=(J)(((__uint128_t)1<<127)-1);
                if(num>max_int/(2*w*w+length2)) return -1;
                J den=J(10000000000LL)*8*r*r*r*r*r;
                J base=num*8/(J(10000000000LL)*r2*r2*r2),loss=(num*(2*w*w+length2)+den-1)/den;
                if(base>loss)total+=(I)(base-loss);
            }
        }
        out[(I)i*ns+j]=total/P/1000; // picorate to nanorate, once per source
    }
    return 0;
}
