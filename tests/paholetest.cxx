#include <cstdint>
#include <cstddef>
#include <string>
#include <iostream>

template<size_t A, size_t B>
struct X
{

enum : size_t { a = A };
enum : size_t { b = B };

};


struct innerst
{
	int i;
	double po;
};

struct bftest
{
	bool x : 3;
	bool z : 17;
	uint32_t xx;
	uint16_t abc;
	uint32_t xx7;
	uint8_t okz;
	uint16_t adbc;
	bool u : 4;
};

struct gnah
{
	char c;
	innerst i;
	double x;
};

struct test
{
	int i;
	char c;
	long oc;
	double x;
	gnah xg;
	bool b;
};

struct small
{
	char c = 'C';
	uint16_t x = 0x8787;
	char h = 'H';
};

struct big
{
	uint64_t n = 0x7272727272727272;
};

struct more
{
	small s;
	big b;
	uint64_t y = 0x4b4b4b4b4b4b4b4b;
	uint16_t p = 0x1515;
};

struct morev : virtual small, virtual big, virtual innerst
{
	uint64_t y = 0x4b4b4b4b4b4b4b4b;
	uint16_t p = 0x1515;
	char u = 'U';
//	char fillbuf[117];
};


struct b00
{
	int x00 = 0xb0b0b0b0;
	char c00 = 'B';
};
struct b0
{
	int x0 = 0xbabababa;
	char c0 = 'X';
};

struct g00
{
	int x00 = 0xb0b0b0b0;
	char c00 = 'B';
	uint64_t g00 = 0x5656565656565656;
};
struct g0
{
	int x0 = 0xbabababa;
	char c0 = 'X';
	uint64_t g0 = 0x1f1f1f1f1f1f1f1f;
	uint8_t bop;
};



struct b1 : b0
{
	int x1;
	char c1;
};

struct b2 : b1 
{
	int x2;
	char c2;
	g0 g;
};

struct bb : b0,b00
{
};

struct bv : virtual b0, virtual b00
{
};

struct gv : virtual g0, virtual g00
{
};

struct xv : b00, virtual b0, virtual g0
{
};

struct oax : virtual b0, virtual g0, virtual b00, virtual g00
{
};

test t;
bb b;
bv v;
gv vg;
b2 bb;
xv x;
more m;
morev vm;
oax xxx;

struct f0
{
	char c;
	uint32_t x;
	virtual ~f0(){}
};


struct f1 : f0
{
	char c;
	uint32_t x;
	virtual ~f1(){}
};

template<class T>
struct f2 : f1,f0
{
	char c;
	uint32_t x;
	virtual ~f2(){}
	char o;
};

struct f3 : f2<X<43,42>>
{
	int m;
};

struct cm
{
	char m0;
};

struct sb
{
	char s0;
};

struct sx : sb
{
	char x0;
	cm c0;
};

f2<X<43,42>> f;
f0* ff = (f1*)&f;

f1 fe;
f0* fe0 = (f0*)&fe;

f3 fd;
sx s;

bftest bft;
struct u
{
	int x;
	union {
		double b;
		int a;
	} n;
};
u uu;
int main(int argc, const char *argv[])
{
	std::string s;
	char* vmbase = (char*)&vm;
	std::cout << "(void*)vmbase = " << (void*)vmbase << "\n";
	char* c = (char*)&vm.c;
	std::cout << "(void*)c = " << (void*)c << "\n";
	std::cout << "(void*)(c-vmbase) = " << (void*)(c-vmbase) << "\n";
	
	
	
}
// vim: tabstop=4 shiftwidth=4 noexpandtab
